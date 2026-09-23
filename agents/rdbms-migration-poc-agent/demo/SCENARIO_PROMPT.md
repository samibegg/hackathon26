# Demo Data Scenario Prompt

Use this prompt to turn an end user's description into a reviewed scenario for the
fixed five-table e-commerce demo. The generator creates **realistic synthetic data**;
do not use names, emails, payments, or other personal data from a production system.

```text
Create a JSON scenario for a realistic synthetic e-commerce dataset. The existing
migration demo requires these entities: customers, products, orders, order_items, and
payments. Do not add tables or fields.

End-user requirements:
<describe the business, catalog, customer geography, order volume, currency, order
statuses, date range, and typical number of items per order>

Return JSON only, matching this shape:
{
  "version": 1,
  "profile": "short business description",
  "seed": 12345,
  "reference_date": "2026-01-01T00:00:00+00:00",
  "counts": { "customers": 2000, "products": 500, "orders": 5000 },
  "country_weights": { "US": 70, "CA": 20, "GB": 10 },
  "currency": "USD",
  "order_status_weights": {
    "delivered": 55, "shipped": 20, "pending": 15, "cancelled": 10
  },
  "line_items_per_order": { "min": 1, "max": 5 },
  "date_range_days": 365
}

Constraints: use positive integer counts, a fixed ISO-8601 reference date and integer
seed, three-letter ISO currency, two-letter country codes, positive weights, and 1-10
line items per order. This data is synthetic and must be reviewed before it is used.
```

Save the reviewed JSON as `demo/scenario.json`, then run:

```bash
./scripts/seed-postgres-demo.sh --reset
```
