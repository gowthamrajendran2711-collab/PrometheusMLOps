# PrometheusMLOps Error Log

## [ERR-001] Ray worker OOM during distributed training
**Date:** 2024-02-14 | **Severity:** High | **Status:** Resolved

**Description:** Ray workers OOMed on gradient accumulation with batch_size=128 across 8 GPUs.
**Root Cause:** Gradient tensors held in memory longer than expected due to custom backward hook.
**Fix:** Added `torch.cuda.empty_cache()` after each accumulation step + reduced batch_size to 64.
**Impact:** Training stable at 91.3% GPU utilization with no OOM events.

---

## [ERR-002] MLflow artifact upload failures to S3 on large models
**Date:** 2024-03-01 | **Severity:** Medium | **Status:** Resolved

**Description:** Models > 2GB failed to upload to S3 MLflow artifact store with `ConnectionResetError`.
**Root Cause:** boto3 default multipart threshold was too high (8MB), causing single-part uploads for huge files.
**Fix:** Set `MLFLOW_S3_UPLOAD_EXTRA_ARGS` with multipart_threshold=50MB and max_concurrency=10.
**Impact:** 340M param model uploads in 3.2 min, no failures in 200+ subsequent uploads.

---

## [ERR-003] Airflow DAG scheduling drift
**Date:** 2024-03-20 | **Severity:** Low | **Status:** Resolved

**Description:** Training DAG drifted 40+ min from scheduled 2 AM start over 2 weeks.
**Root Cause:** Airflow scheduler pool was saturated by concurrent sensor tasks holding slots.
**Fix:** Increased default pool slots from 128 to 256. Added dedicated pool for sensors.
**Impact:** DAG starts within 2 min of schedule consistently.

---

## [ERR-004] Helm upgrade caused 90s downtime on model server
**Date:** 2024-04-10 | **Severity:** High | **Status:** Resolved

**Description:** `helm upgrade` with new model weights caused 90s of 503 errors during rollout.
**Root Cause:** maxUnavailable=1 with only 2 replicas meant 50% capacity loss during upgrade. Model load took 70s.
**Fix:** Added preStop hook + increased minReadySeconds=90. Set PodDisruptionBudget minAvailable=2.
**Impact:** Zero-downtime deploys with rolling update, P95 latency unaffected.
