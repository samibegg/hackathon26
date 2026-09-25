"""Deterministic Postgres → MongoDB migration runner."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

import psycopg
from pymongo import MongoClient

from agent_rdbms_migration_poc.migration.mongo_conn import (
    mongodb_uri_kind,
    resolve_migration_mongodb_uri,
    resolve_migration_target_db,
)
from agent_rdbms_migration_poc.migration.postgres_conn import (
    connect_postgres,
    resolve_postgres_uri,
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _row_to_doc(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _json_safe(v) for k, v in row.items()}


def _fetch_table(conn: psycopg.Connection, table: str) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(f'SELECT * FROM "{table}"')  # noqa: S608 — PoC fixed table names from plan
        return [dict(r) for r in cur.fetchall()]


def _apply_indexes(collection, index_specs: list[dict]) -> None:
    for spec in index_specs:
        keys = spec.get("keys", {})
        collection.create_index(list(keys.items()), unique=bool(spec.get("unique", False)))


def run_migration(plan: dict[str, Any]) -> dict[str, Any]:
    postgres_uri = resolve_postgres_uri()
    mongo_uri = resolve_migration_mongodb_uri()
    target_db = resolve_migration_target_db(
        plan.get("target", {}).get("database", "commerce_poc"),
    )

    if not postgres_uri:
        raise RuntimeError("POSTGRES_URI is required for migration execution")
    if not mongo_uri:
        raise RuntimeError(
            "Migration MongoDB URI required — set MONGODB_URI (Atlas) in .env "
            "or MIGRATION_TARGET_MONGODB_URI"
        )

    stats: dict[str, Any] = {
        "collections_written": {},
        "indexes_created": [],
        "target_database": target_db,
        "target_uri_kind": mongodb_uri_kind(mongo_uri),
    }

    with connect_postgres(postgres_uri) as pg_conn:
        mongo = MongoClient(mongo_uri)
        db = mongo[target_db]

        for coll_spec in plan.get("collections", []):
            name = coll_spec["name"]
            source_table = coll_spec["source_table"]
            pattern = coll_spec.get("pattern", "one_to_one")
            collection = db[name]
            collection.delete_many({})

            if pattern == "one_to_one":
                docs = [_row_to_doc(r) for r in _fetch_table(pg_conn, source_table)]
                if docs:
                    collection.insert_many(docs)
                stats["collections_written"][name] = len(docs)
            elif pattern == "bucket_embed":
                orders = _fetch_table(pg_conn, source_table)
                embed_spec = (coll_spec.get("embedded_children") or [None])[0]
                if not embed_spec:
                    raise RuntimeError(f"bucket_embed collection {name} missing embedded_children")
                child_table = embed_spec["source_table"]
                fk = embed_spec["foreign_key"]
                array_field = embed_spec["array_field"]
                exclude = set(embed_spec.get("exclude_columns", []))

                children = _fetch_table(pg_conn, child_table)
                by_parent: dict[Any, list[dict]] = defaultdict(list)
                for child in children:
                    parent_id = child[fk]
                    item = {k: _json_safe(v) for k, v in child.items() if k not in exclude}
                    by_parent[parent_id].append(item)

                docs = []
                for order in orders:
                    doc = _row_to_doc(order)
                    pk = coll_spec.get("primary_key", "order_id")
                    doc[array_field] = by_parent.get(order[pk], [])
                    docs.append(doc)
                if docs:
                    collection.insert_many(docs)
                stats["collections_written"][name] = len(docs)
            else:
                raise RuntimeError(f"Unsupported pattern: {pattern}")

            for idx in coll_spec.get("indexes", []):
                _apply_indexes(collection, [idx])
                stats["indexes_created"].append({"collection": name, "keys": idx.get("keys")})

    return stats


def run_validation(plan: dict[str, Any]) -> dict[str, Any]:
    postgres_uri = resolve_postgres_uri()
    mongo_uri = resolve_migration_mongodb_uri()
    target_db = resolve_migration_target_db(
        plan.get("target", {}).get("database", "commerce_poc"),
    )
    if not postgres_uri or not mongo_uri:
        raise RuntimeError("POSTGRES_URI and migration MongoDB URI are required for validation")

    checks: list[dict[str, Any]] = []
    passed = True

    with connect_postgres(postgres_uri) as pg_conn:
        mongo = MongoClient(mongo_uri)
        db = mongo[target_db]

        for table in plan.get("validation", {}).get("row_count_tables", []):
            coll_name = table if table != "order_items" else None
            if coll_name:
                with pg_conn.cursor() as cur:
                    cur.execute(f'SELECT COUNT(*) FROM "{table}"')  # noqa: S608
                    pg_count = cur.fetchone()[0]
                mongo_count = db[coll_name].count_documents({})
                ok = pg_count == mongo_count
                passed = passed and ok
                checks.append(
                    {
                        "check": "row_count",
                        "source_table": table,
                        "target_collection": coll_name,
                        "postgres_count": pg_count,
                        "mongo_count": mongo_count,
                        "passed": ok,
                    }
                )

        embed = plan.get("validation", {}).get("embedded_integrity")
        if embed:
            parent_coll = embed["parent_collection"]
            child_table = embed["child_table"]
            array_field = embed["array_field"]
            parent_key = embed["parent_key"]
            with pg_conn.cursor() as cur:
                cur.execute(f'SELECT COUNT(*) FROM "{child_table}"')  # noqa: S608
                pg_items = cur.fetchone()[0]
            mongo_items = 0
            for doc in db[parent_coll].find({}, {array_field: 1}):
                mongo_items += len(doc.get(array_field, []))
            ok = pg_items == mongo_items
            passed = passed and ok
            checks.append(
                {
                    "check": "embedded_line_items_integrity",
                    "postgres_order_items": pg_items,
                    "mongo_embedded_items": mongo_items,
                    "passed": ok,
                }
            )
            orphan_orders = db[parent_coll].count_documents({array_field: {"$size": 0}})
            checks.append(
                {
                    "check": "orders_with_empty_line_items",
                    "count": orphan_orders,
                    "passed": orphan_orders == 0,
                }
            )
            if orphan_orders != 0:
                passed = False

    return {"passed": passed, "checks": checks}
