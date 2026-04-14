import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_project.settings')
django.setup()

from django.db import connection

sql1 = """
CREATE TABLE IF NOT EXISTS orders (
    id bigint AUTO_INCREMENT PRIMARY KEY,
    customer_id bigint NOT NULL,
    address longtext NOT NULL,
    payment_method varchar(50) NOT NULL,
    total_amount decimal(12, 2) NOT NULL,
    created_at datetime(6) NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
);
"""

sql2 = """
CREATE TABLE IF NOT EXISTS order_items (
    id bigint AUTO_INCREMENT PRIMARY KEY,
    order_id bigint NOT NULL,
    product_id int NOT NULL,
    product_type varchar(50) NOT NULL,
    product_name varchar(255) NOT NULL,
    product_price decimal(12, 2) NOT NULL,
    quantity int NOT NULL,
    FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
);
"""

with connection.cursor() as cursor:
    cursor.execute(sql1)
    cursor.execute(sql2)

print("Orders tables created successfully!")
