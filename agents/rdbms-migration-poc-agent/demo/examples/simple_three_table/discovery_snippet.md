# Discovery snippet — simple order subset

**Source:** PostgreSQL, tables `customers`, `orders`, `order_lines`.

**Access pattern:** Order detail screen always loads the order and all line items together; customer profile is a separate API.

**Target:** MongoDB Atlas, database `commerce_poc` for PoC.

**Modeling preference:** Embed line items under orders; keep customers as their own collection.

**Validation:** Row counts for `customers` and `orders`; sum of `order_lines` rows equals total embedded line items across orders.
