# Discovery call — Acme Retail (PostgreSQL → MongoDB Atlas)

**Date:** 2026-03-10  
**Attendees:** Customer (Maria Chen, VP Engineering), MongoDB TA (Alex)

## 1. Engagement context and success criteria

Maria: We need a PoC in two weeks showing order history APIs can be served from MongoDB with lower join complexity than Postgres.

Alex: Success = 5 core tables migrated, embedded line items on orders, validation report for leadership.

## 2. Source PostgreSQL environment

Maria: PostgreSQL 15 on RDS, database `commerce_demo`. In scope: `customers`, `products`, `orders`, `order_items`, `payments`. ~25k rows total in PoC subset.

## 3. Schema relationships and access patterns

Maria: Order detail API always loads order header + all line items + product names. Customer profile is separate. Payments queried for audits by `order_id` and date range — compliance wants payments isolated.

## 4. Application landscape

Maria: Node.js monolith today; no immediate app rewrite — PoC is data plane only.

## 5. Data quality and governance

Maria: No PII beyond email/name; payments retain 7 years — separate collection is fine.

## 6. Target MongoDB / Atlas

Maria: Atlas M10, database name `commerce_poc`, us-east-1. Indexes on customer email, order date, payment order_id.

## 7. Target data model preferences

Maria: Prefer embedding line items under orders. Keep products and customers as their own collections. Payments must NOT be embedded.

## 8. Migration approach

Maria: One-time bulk load for PoC; cutover not in scope. Batch acceptable overnight.

## 9. Validation and acceptance

Maria: Row counts must match for customers, products, orders, payments; every order must have `line_items` array length equal to source `order_items` count.

## 10. Risks and next steps

Maria: Risk if we embed wrong child data — need explicit mapping doc. Next: share DDL export and run PoC load.

**Alex:** We'll document embed vs reference rationale and produce a migration plan JSON plus deterministic runner.
