#!/usr/bin/env python3
"""Seed the fixed e-commerce demo schema with deterministic realistic synthetic data."""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "-f", "docker-compose.postgres.yml"]
PSQL = [*COMPOSE, "exec", "-T", "postgres-demo", "psql", "-v", "ON_ERROR_STOP=1", "-U", "commerce", "-d", "commerce_demo"]

FIRST_NAMES = ("Avery", "Casey", "Jordan", "Morgan", "Riley", "Taylor", "Cameron", "Devon")
LAST_NAMES = ("Bennett", "Chen", "Garcia", "Hughes", "Ibrahim", "Kim", "Martin", "Patel")
CATEGORIES = ("Trail", "Summit", "Harbor", "Canyon", "Alpine", "Coastal", "Ridge", "Evergreen")
PRODUCTS = ("Daypack", "Shell Jacket", "Camp Mug", "Hiking Pole", "Trail Shoe", "Dry Bag", "Headlamp", "Merino Tee")
PAYMENT_METHODS = ("card", "digital_wallet", "bank_transfer")


def _require_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


def _weights(value: Any, name: str) -> tuple[list[str], list[int]]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{name} must be a non-empty object")
    labels = list(value)
    weights = [_require_int(weight, f"{name}.{label}", 1, 100_000) for label, weight in value.items()]
    return labels, weights


def load_scenario(path: Path) -> dict[str, Any]:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    if scenario.get("version") != 1:
        raise ValueError("scenario.version must be 1")
    if not isinstance(scenario.get("profile"), str) or not scenario["profile"].strip():
        raise ValueError("scenario.profile must be a non-empty string")
    _require_int(scenario.get("seed"), "seed", 0, 2**32 - 1)
    reference_date = scenario.get("reference_date")
    if not isinstance(reference_date, str):
        raise ValueError("reference_date must be an ISO-8601 timestamp")
    try:
        datetime.fromisoformat(reference_date.replace("Z", "+00:00"))
    except ValueError as err:
        raise ValueError("reference_date must be an ISO-8601 timestamp") from err
    counts = scenario.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("counts must be an object")
    for name in ("customers", "products", "orders"):
        _require_int(counts.get(name), f"counts.{name}", 1, 100_000)
    countries, _ = _weights(scenario.get("country_weights"), "country_weights")
    if any(len(country) != 2 or not country.isalpha() for country in countries):
        raise ValueError("country_weights keys must be two-letter country codes")
    currency = scenario.get("currency")
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
        raise ValueError("currency must be a three-letter ISO code")
    _weights(scenario.get("order_status_weights"), "order_status_weights")
    line_items = scenario.get("line_items_per_order")
    if not isinstance(line_items, dict):
        raise ValueError("line_items_per_order must be an object")
    minimum = _require_int(line_items.get("min"), "line_items_per_order.min", 1, 10)
    _require_int(line_items.get("max"), "line_items_per_order.max", minimum, 10)
    _require_int(scenario.get("date_range_days"), "date_range_days", 1, 3650)
    return scenario


def rows_for(scenario: dict[str, Any]) -> dict[str, list[tuple[Any, ...]]]:
    rng = random.Random(scenario["seed"])
    counts = scenario["counts"]
    countries, country_weights = _weights(scenario["country_weights"], "country_weights")
    statuses, status_weights = _weights(scenario["order_status_weights"], "order_status_weights")
    customer_count, product_count, order_count = (
        counts["customers"], counts["products"], counts["orders"]
    )
    reference_time = datetime.fromisoformat(
        scenario["reference_date"].replace("Z", "+00:00")
    ).astimezone(timezone.utc)
    customers = []
    for customer_id in range(1, customer_count + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        customers.append(
            (
                f"{first.lower()}.{last.lower()}.{customer_id}@example.test",
                f"{first} {last}",
                rng.choices(countries, weights=country_weights)[0],
                reference_time - timedelta(days=rng.randrange(730)),
            )
        )

    products = []
    for product_id in range(1, product_count + 1):
        price_cents = rng.randrange(1800, 28000)
        products.append((f"{scenario['profile'][:3].upper()}-{product_id:06d}", f"{rng.choice(CATEGORIES)} {rng.choice(PRODUCTS)}", f"{price_cents / 100:.2f}", rng.random() > 0.04))

    orders: list[tuple[Any, ...]] = []
    order_items: list[tuple[Any, ...]] = []
    payments: list[tuple[Any, ...]] = []
    item_range = scenario["line_items_per_order"]
    for order_id in range(1, order_count + 1):
        order_date = reference_time - timedelta(
            days=rng.randrange(scenario["date_range_days"]), hours=rng.randrange(24)
        )
        orders.append(
            (
                rng.randint(1, customer_count),
                rng.choices(statuses, weights=status_weights)[0],
                order_date,
                scenario["currency"].upper(),
            )
        )
        total_cents = 0
        for _ in range(rng.randint(item_range["min"], item_range["max"])):
            product_id = rng.randint(1, product_count)
            price = products[product_id - 1][2]
            quantity = rng.randint(1, 4)
            total_cents += int(float(price) * 100) * quantity
            order_items.append((order_id, product_id, quantity, price))
        payments.append((order_id, f"{total_cents / 100:.2f}", rng.choice(PAYMENT_METHODS), order_date + timedelta(minutes=rng.randint(5, 180))))
    return {"products": products, "customers": customers, "orders": orders, "order_items": order_items, "payments": payments}


def psql(sql: str) -> None:
    subprocess.run(PSQL, cwd=ROOT, input=sql, text=True, check=True)


def copy_rows(table: str, columns: str, rows: list[tuple[Any, ...]]) -> None:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    psql(f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv);\n{buffer.getvalue()}\\.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=ROOT / "demo" / "scenario.json")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate the demo schema before loading data")
    args = parser.parse_args()
    scenario = load_scenario(args.scenario)
    data = rows_for(scenario)
    if not args.reset:
        raise SystemExit("Refusing to overwrite data without --reset")
    psql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    psql((ROOT / "demo" / "schema.sql").read_text(encoding="utf-8"))
    copy_rows("products", "sku, name, unit_price, active", data["products"])
    copy_rows("customers", "email, full_name, country_code, created_at", data["customers"])
    copy_rows("orders", "customer_id, order_status, order_date, currency", data["orders"])
    copy_rows("order_items", "order_id, product_id, quantity, unit_price", data["order_items"])
    copy_rows("payments", "order_id, amount, payment_method, paid_at", data["payments"])
    print(json.dumps({"profile": scenario["profile"], "rows": {name: len(rows) for name, rows in data.items()}}, indent=2))


if __name__ == "__main__":
    main()
