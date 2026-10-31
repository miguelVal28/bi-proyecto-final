from bi_proyecto_final_etl.flow import _transform_records


def test_transform_records_normalizes_name_and_sets_active_flag():
    records = [{"id": 10, "name": "  gAMma ", "value": 1}]

    transformed = _transform_records(records)

    assert transformed == [{"id": 10, "name": "Gamma", "value": 1, "is_active": True}]
