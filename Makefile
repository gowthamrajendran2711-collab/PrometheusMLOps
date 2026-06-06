.PHONY: install test lint docker-build clean

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

docker-build:
	docker build -t prometheusmlops:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete

train:
	python -m src.training.train --config configs/experiment.yaml

airflow:
	airflow dags trigger prometheus_training_pipeline
