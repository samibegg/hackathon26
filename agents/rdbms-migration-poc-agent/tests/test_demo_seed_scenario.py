import importlib.util
from pathlib import Path


def _load_seed_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "seed-postgres-scenario.py"
    spec = importlib.util.spec_from_file_location("seed_postgres_scenario", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scenario_generates_deterministic_valid_rows() -> None:
    module = _load_seed_module()
    scenario = module.load_scenario(Path(__file__).resolve().parents[1] / "demo" / "scenario.json")

    first = module.rows_for(scenario)
    second = module.rows_for(scenario)

    assert first == second
    assert len(first["customers"]) == scenario["counts"]["customers"]
    assert len(first["products"]) == scenario["counts"]["products"]
    assert len(first["orders"]) == scenario["counts"]["orders"]
    assert len(first["payments"]) == len(first["orders"])
    assert all(item[2] > 0 for item in first["order_items"])
