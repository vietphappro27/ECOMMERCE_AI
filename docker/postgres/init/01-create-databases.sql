SELECT 'CREATE DATABASE ktra1_product_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ktra1_product_db')
\gexec

SELECT 'CREATE DATABASE ktra1_cart_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ktra1_cart_db')
\gexec

SELECT 'CREATE DATABASE ktra1_ai_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ktra1_ai_db')
\gexec

SELECT 'CREATE DATABASE ktra1_order_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ktra1_order_db')
\gexec

SELECT 'CREATE DATABASE ktra1_payment_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ktra1_payment_db')
\gexec

SELECT 'CREATE DATABASE ktra1_ship_db'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ktra1_ship_db')
\gexec
