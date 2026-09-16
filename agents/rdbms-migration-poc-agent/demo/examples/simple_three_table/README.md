# Simple three-table example

A minimal relational model for workshops and Playground walkthroughs.

## Tables

| Table | Role |
|-------|------|
| `customers` | Master data (1:1 → MongoDB `customers`) |
| `orders` | Order header |
| `order_lines` | Line items (typically **embedded** under `orders` as `line_items[]`) |

## Suggested MongoDB shape

```text
customers   (collection, 1:1 from customers)
orders      (collection, embed order_lines → line_items[])
```

## Agent tools

- `list_ddl_examples` — catalog of bundled DDL samples
- `load_ddl_example("simple_three_table")` — load this DDL into the session
- `get_example_postgres_ddl("simple_three_table")` — return DDL text only

Full **deterministic migration** (`execute_migration_pipeline`) still requires the 5-table `ecommerce_mvp` demo and `demo/schema.sql`.
