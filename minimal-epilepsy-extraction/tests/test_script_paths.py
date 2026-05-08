from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_broader_runner_default_data_points_to_bundled_dataset() -> None:
    runner = _load_script("run_broader_field_experiment")

    args = runner.build_parser().parse_args([])

    assert args.data == "data/synthetic_data_subset_1500.json"
    assert (ROOT / args.data).exists()


def test_broader_runner_treats_bundled_dataset_as_canonical() -> None:
    runner = _load_script("run_broader_field_experiment")

    policy = runner._artifact_policy(ROOT / "data" / "synthetic_data_subset_1500.json", False)

    assert policy["synthetic_canonical_dataset"] is True
    assert policy["persist_quoted_evidence"] is True
    assert policy["redacted"] is False


def test_adjudication_generator_resolves_defaults_from_capsule_root() -> None:
    generator = _load_script("generate_adjudication_worksheet")

    data_path = generator.resolve_capsule_path("data/synthetic_data_subset_1500.json")
    out_dir = generator.resolve_capsule_path("docs/adjudication")

    assert data_path == ROOT / "data" / "synthetic_data_subset_1500.json"
    assert data_path.exists()
    assert out_dir == ROOT / "docs" / "adjudication"
