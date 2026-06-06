"""Tests for PrometheusMLOps training pipeline"""
import pytest
from unittest.mock import MagicMock, patch

def test_experiment_tracker_logs_params():
    with patch("mlflow.start_run"), patch("mlflow.log_params") as mock_log,          patch("mlflow.end_run"), patch("mlflow.set_tracking_uri"), patch("mlflow.set_experiment"):
        from src.tracking.experiment import ExperimentTracker
        tracker = ExperimentTracker()
        with tracker:
            tracker.log_params({"lr": 0.001, "epochs": 10})
        mock_log.assert_called_once_with({"lr": 0.001, "epochs": 10})

def test_model_server_predict_missing_version():
    from fastapi.testclient import TestClient
    from src.serving.server import app
    client = TestClient(app)
    r = client.post("/predict", json={"inputs": [[1.0, 2.0]], "model_version": "nonexistent"})
    assert r.status_code == 404

def test_model_server_health():
    from fastapi.testclient import TestClient
    from src.serving.server import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
