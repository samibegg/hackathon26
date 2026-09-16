-- Demo seed: ~25k rows total (2k customers, 500 products, 5k orders, ~15k line items, 5k payments)

INSERT INTO products (sku, name, unit_price)
SELECT
    'SKU-' || LPAD(i::text, 6, '0'),
    'Product ' || i,
    (10 + (i % 90))::numeric(12, 2)
FROM generate_series(1, 500) AS i;

INSERT INTO customers (email, full_name, country_code)
SELECT
    'user' || i || '@example.com',
    'Customer ' || i,
    CASE WHEN i % 5 = 0 THEN 'CA' ELSE 'US' END
FROM generate_series(1, 2000) AS i;

INSERT INTO orders (customer_id, order_status, order_date, currency)
SELECT
    1 + (i % 2000),
    CASE i % 4
        WHEN 0 THEN 'shipped'
        WHEN 1 THEN 'pending'
        WHEN 2 THEN 'cancelled'
        ELSE 'delivered'
    END,
    NOW() - ((i % 365) || ' days')::interval,
    'USD'
FROM generate_series(1, 5000) AS i;

INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT
    1 + ((i - 1) / 3),
    1 + (i % 500),
    1 + (i % 4),
    (SELECT unit_price FROM products WHERE product_id = 1 + (i % 500))
FROM generate_series(1, 15000) AS i;

INSERT INTO payments (order_id, amount, payment_method, paid_at)
SELECT
    o.order_id,
    COALESCE((
        SELECT SUM(oi.quantity * oi.unit_price)
        FROM order_items oi
        WHERE oi.order_id = o.order_id
    ), 0),
    CASE o.order_id % 3 WHEN 0 THEN 'card' WHEN 1 THEN 'paypal' ELSE 'wire' END,
    o.order_date + interval '1 hour'
FROM orders o;
