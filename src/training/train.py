"""Distributed Training Entry Point"""
import argparse, yaml
import mlflow
import ray
from ray import train
from ray.train.torch import TorchTrainer
from ray.train import ScalingConfig

def train_func(config: dict):
    """Per-worker training function."""
    import torch
    from torch.utils.data import DataLoader

    model = build_model(config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["lr"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=config["epochs"])

    for epoch in range(config["epochs"]):
        train_loss = train_epoch(model, optimizer, config)
        val_metrics = evaluate(model, config)

        train.report({
            "epoch": epoch,
            "train_loss": train_loss,
            **val_metrics
        })
        scheduler.step()

def build_model(config): pass
def train_epoch(model, optimizer, config): return 0.0
def evaluate(model, config): return {"val_loss": 0.0, "accuracy": 0.0}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--tracking-uri", default="http://localhost:5000")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    mlflow.set_tracking_uri(args.tracking_uri)

    with mlflow.start_run(run_name=config.get("experiment_name", "run")):
        mlflow.log_params(config)
        ray.init()
        trainer = TorchTrainer(
            train_loop_per_worker=train_func,
            train_loop_config=config,
            scaling_config=ScalingConfig(num_workers=config.get("num_gpus", 1), use_gpu=True)
        )
        result = trainer.fit()
        mlflow.log_metrics(result.metrics)
        print(f"Training complete: {result.metrics}")

if __name__ == "__main__":
    main()
