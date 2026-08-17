import re
import json
import httpx
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass
import math


@dataclass
class DiffHunk:
    filename: str
    language: str
    start_line: int
    code: str
    patch: str


@dataclass
class ReviewComment:
    filename: str
    line: int
    severity: str      
    category: str       
    message: str
    suggestion: Optional[str] = None   


REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer. Analyze the provided code diff and identify:
1. Bugs (logic errors, edge cases, null pointer risks, race conditions)
2. Security vulnerabilities (injection, hardcoded secrets, SSRF, insecure deserialization)
3. Performance issues (N+1 queries, O(n²) where O(n) is possible, missing caching)
4. Readability issues (overly complex logic, missing docstrings, poor naming)
5. Good patterns worth acknowledging (praise good code explicitly)

Rules:
- Only comment on CHANGED lines (marked with + in the diff)
- Be specific: reference the exact line and explain WHY it's a problem
- For security issues: explain the attack vector
- Suggest a fix when possible
- Skip trivial style issues (formatting, whitespace) unless they affect readability
- If the code is clean, say so — don't invent issues

Return ONLY valid JSON in this exact format:
{
  "comments": [
    {
      "line": <int, line number in the file>,
      "severity": "<critical|warning|suggestion|praise>",
      "category": "<bug|security|performance|readability|positive>",
      "message": "<clear explanation of the issue and why it matters>",
      "suggestion": "<optional: improved code or approach>"
    }
  ],
  "summary": "<2-3 sentence overall assessment>"
}"""


class DiffParser:
    """Parse GitHub unified diff format into reviewable hunks."""

    LANGUAGE_MAP = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".java": "java", ".go": "go", ".rs": "rust", ".cpp": "cpp",
        ".c": "c", ".cs": "csharp", ".rb": "ruby", ".php": "php"
    }

    SKIP_PATTERNS = [
        r"package-lock\.json$", r"yarn\.lock$", r"\.min\.js$",
        r"__pycache__", r"\.pyc$", r"dist/", r"build/"
    ]

    def should_skip(self, filename: str) -> bool:
        return any(re.search(p, filename) for p in self.SKIP_PATTERNS)

    def get_language(self, filename: str) -> str:
        ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
        return self.LANGUAGE_MAP.get(ext, "text")

    def parse_pr_files(self, pr_files: List[Dict]) -> List[DiffHunk]:
        """
        Parse GitHub API /pulls/{n}/files response into DiffHunks.
        Each file has: filename, patch (unified diff), status (added/modified/removed)
        """
        hunks = []
        for file in pr_files:
            filename = file.get("filename", "")
            if self.should_skip(filename):
                continue
            if file.get("status") == "removed":
                continue

            patch = file.get("patch", "")
            if not patch:
                continue

            added_lines = []
            current_line = 0

            for line in patch.split("\n"):
                if line.startswith("@@"):
                    # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
                    match = re.search(r"\+(\d+)", line)
                    current_line = int(match.group(1)) if match else 0
                elif line.startswith("+") and not line.startswith("+++"):
                    added_lines.append((current_line, line[1:]))
                    current_line += 1
                elif not line.startswith("-"):
                    current_line += 1

            if added_lines:
                start_line = added_lines[0][0]
                code = "\n".join(code for _, code in added_lines)
                hunks.append(DiffHunk(
                    filename=filename,
                    language=self.get_language(filename),
                    start_line=start_line,
                    code=code,
                    patch=patch[:3000]
                ))

        return hunks


class SecretScanner:
    """
    Fast regex pre-scan for secrets before sending to LLM.
    Catches API keys, passwords, tokens that should never be in code.
    """
    PATTERNS = {
        "aws_key": r"AKIA[0-9A-Z]{16}",
        "github_token": r"ghp_[a-zA-Z0-9]{36}",
        "private_key": r"-----BEGIN (RSA |EC )?PRIVATE KEY-----",
        "generic_secret": r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]{8,}['\"]",
        "anthropic_key": r"sk-ant-[a-zA-Z0-9\-]{32,}",
    }

    def scan(self, code: str) -> List[Dict]:
        findings = []
        for name, pattern in self.PATTERNS.items():
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                findings.append({
                    "type": name,
                    "match": match.group()[:20] + "...", 
                    "position": match.start()
                })
        return findings


class LLMReviewer:
    """
    Sends code to Claude for review and parses structured response.
    """
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.client = httpx.AsyncClient(timeout=60.0)
        self.secret_scanner = SecretScanner()

    async def review_hunk(self, hunk: DiffHunk) -> List[ReviewComment]:
        """Review a single diff hunk."""

        # Pre-scan for secrets (cheap, fast)
        secrets = self.secret_scanner.scan(hunk.code)
        secret_comments = [
            ReviewComment(
                filename=hunk.filename,
                line=hunk.start_line,
                severity="critical",
                category="security",
                message=f"Potential secret detected: {s['type']}. Never commit credentials to source control.",
                suggestion="Use environment variables or a secrets manager (AWS Secrets Manager, HashiCorp Vault)"
            )
            for s in secrets
        ]

        user_prompt = f"""Review this {hunk.language} code diff from file `{hunk.filename}` (starts at line {hunk.start_line}):

```{hunk.language}
{hunk.patch[:4000]}
```

Lines start at {hunk.start_line}. Return JSON only."""

        try:
            response = await self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": self.model,
                    "max_tokens": 2000,
                    "temperature": 0,   # deterministic reviews
                    "system": REVIEW_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}]
                }
            )
            response.raise_for_status()
            content = response.json()["content"][0]["text"]

            # Parse JSON response
            data = json.loads(content)
            llm_comments = [
                ReviewComment(
                    filename=hunk.filename,
                    line=c.get("line", hunk.start_line),
                    severity=c.get("severity", "suggestion"),
                    category=c.get("category", "readability"),
                    message=c.get("message", ""),
                    suggestion=c.get("suggestion")
                )
                for c in data.get("comments", [])
            ]
            return secret_comments + llm_comments

        except (json.JSONDecodeError, KeyError, httpx.HTTPError) as e:
            print(f"Review error for {hunk.filename}: {e}")
            return secret_comments

    async def review_pr(self, pr_files: List[Dict]) -> List[ReviewComment]:
        """Review all files in a PR concurrently."""
        parser = DiffParser()
        hunks = parser.parse_pr_files(pr_files)

        if not hunks:
            return []

        
        tasks = [self.review_hunk(hunk) for hunk in hunks[:20]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_comments = []
        for result in results:
            if isinstance(result, list):
                all_comments.extend(result)

        # Sort by severity (critical first)
        severity_order = {"critical": 0, "warning": 1, "suggestion": 2, "praise": 3}
        all_comments.sort(key=lambda c: severity_order.get(c.severity, 99))
        return all_comments
