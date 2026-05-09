from pathlib import Path

from epilepsy_extraction.data import load_synthetic_subset, iter_records, select_fixed_slice
from epilepsy_extraction.schemas import GoldRecord


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_subset_fixture.json"


def _record(index: int, row_ok: bool = True) -> GoldRecord:
    return GoldRecord(
        source_row_index=index,
        letter=f"letter {index}",
        gold_label="unknown",
        gold_evidence="",
        row_ok=row_ok,
        raw={},
    )


def test_iter_records_limit_zero_returns_no_rows() -> None:
    assert list(iter_records([_record(1)], limit=0)) == []


def test_iter_records_negative_limit_returns_no_rows() -> None:
    assert list(iter_records([_record(1)], limit=-1)) == []


def test_iter_records_applies_limit_after_row_ok_filter() -> None:
    records = [_record(1, row_ok=False), _record(2), _record(3)]

    result = list(iter_records(records, limit=1, row_ok_only=True))

    assert [record.source_row_index for record in result] == [2]


def test_select_fixed_slice_keeps_requested_row_order_from_source() -> None:
    records = [_record(1), _record(2), _record(3)]

    result = select_fixed_slice(records, row_ids=["3", "1"])

    assert [record.row_id for record in result] == ["1", "3"]


def test_load_synthetic_subset_fixture_shape() -> None:
    records = load_synthetic_subset(FIXTURE_PATH)

    assert len(records) == 3
    assert records[0].row_id == "1"
    assert records[0].gold_label == "2 per month"
    assert records[2].row_ok is False
