"""Airflow DAG: Full training pipeline"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "ml-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
}

with DAG(
    dag_id="prometheus_training_pipeline",
    default_args=default_args,
    schedule_interval="0 2 * * *",  # Daily at 2 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["mlops", "training"],
) as dag:

    validate_data = PythonOperator(
        task_id="validate_data",
        python_callable=lambda: print("Data validation passed"),
    )

    run_training = BashOperator(
        task_id="run_training",
        bash_command="python -m src.training.train --config /opt/configs/experiment.yaml",
    )

    run_evaluation = BashOperator(
        task_id="run_evaluation",
        bash_command="python -m src.eval.evaluate --run-id {{ task_instance.xcom_pull(task_ids=\'run_training\', key=\'run_id\') }}",
    )

    promote_model = PythonOperator(
        task_id="promote_model",
        python_callable=lambda **ctx: print(f"Promoting model from run {ctx[\'ti\'].xcom_pull(\'run_training\')}"),
    )

    validate_data >> run_training >> run_evaluation >> promote_model
