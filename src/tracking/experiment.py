"""MLflow experiment tracking wrapper"""
import mlflow
import mlflow.pytorch
from pathlib import Path
from typing import Any
import json

class ExperimentTracker:
    def __init__(self, tracking_uri: str = "http://localhost:5000", experiment_name: str = "default"):
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)

    def __enter__(self):
        self.run = mlflow.start_run()
        return self

    def __exit__(self, *args):
        mlflow.end_run()

    def log_params(self, params: dict) -> None:
        mlflow.log_params(params)

    def log_metrics(self, metrics: dict, step: int = None) -> None:
        mlflow.log_metrics(metrics, step=step)

    def log_model(self, model, artifact_path: str = "model") -> str:
        mlflow.pytorch.log_model(model, artifact_path)
        return f"{mlflow.get_artifact_uri()}/{artifact_path}"

    def log_artifact(self, path: str) -> None:
        mlflow.log_artifact(path)

    def register_model(self, model_uri: str, name: str, stage: str = "Staging") -> None:
        client = mlflow.tracking.MlflowClient()
        result = mlflow.register_model(model_uri, name)
        client.transition_model_version_stage(name=name, version=result.version, stage=stage)
        print(f"Registered {name} v{result.version} → {stage}")
