from typing import Any

from prefect import flow, get_run_logger, task


def _transform_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **record,
            "name": str(record.get("name", "")).strip().title(),
            "is_active": bool(record.get("value", 0)),
        }
        for record in records
    ]


@task
def extract() -> list[dict[str, Any]]:
    return [
        {"id": 1, "name": "alpha", "value": 10},
        {"id": 2, "name": "beta", "value": 0},
    ]


@task
def transform(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _transform_records(records)


@task
def load(records: list[dict[str, Any]]) -> int:
    logger = get_run_logger()
    logger.info("Loaded %s records", len(records))
    return len(records)


@flow(name="sample-etl-flow")
def etl_flow() -> int:
    records = extract()
    transformed = transform(records)
    return load(transformed)


if __name__ == "__main__":
    etl_flow()
