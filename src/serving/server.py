"""FastAPI model serving endpoint with shadow deployment support"""
import time, asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, make_asgi_app
import structlog

logger = structlog.get_logger(__name__)
app = FastAPI(title="PrometheusMLOps Model Server", version="1.0.0")
app.mount("/metrics", make_asgi_app())

REQUESTS = Counter("model_requests_total", "Total inference requests", ["model_version", "status"])
LATENCY  = Histogram("model_inference_seconds", "Inference latency", ["model_version"])

class PredictRequest(BaseModel):
    inputs: list
    model_version: str = "production"

class PredictResponse(BaseModel):
    predictions: list
    model_version: str
    latency_ms: float

_models = {}  # version → loaded model

def load_model(version: str, artifact_uri: str):
    import mlflow.pytorch
    _models[version] = mlflow.pytorch.load_model(artifact_uri)
    logger.info("model_loaded", version=version)

@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    if req.model_version not in _models:
        raise HTTPException(404, f"Model version {req.model_version!r} not loaded")
    start = time.time()
    try:
        model = _models[req.model_version]
        preds = _run_inference(model, req.inputs)
        latency_ms = (time.time()-start)*1000
        LATENCY.labels(model_version=req.model_version).observe(latency_ms/1000)
        REQUESTS.labels(model_version=req.model_version, status="success").inc()
        # Shadow traffic to staging model if loaded
        if "staging" in _models and req.model_version == "production":
            asyncio.create_task(_shadow_predict(req.inputs))
        return PredictResponse(predictions=preds, model_version=req.model_version, latency_ms=latency_ms)
    except Exception as e:
        REQUESTS.labels(model_version=req.model_version, status="error").inc()
        raise HTTPException(500, str(e))

def _run_inference(model, inputs: list) -> list:
    import torch
    with torch.no_grad():
        t = torch.tensor(inputs)
        return model(t).tolist()

async def _shadow_predict(inputs: list):
    try:
        _run_inference(_models["staging"], inputs)
    except Exception:
        pass  # Shadow failures are silent

@app.get("/health")
async def health(): return {"status": "ok", "loaded_versions": list(_models.keys())}
