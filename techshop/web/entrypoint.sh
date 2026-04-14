#!/bin/bash
set -e

echo "=== TechShop Web Entrypoint ==="

# Chờ MySQL sẵn sàng (retry đơn giản)
echo "Đợi MySQL khởi động..."
for i in $(seq 1 30); do
    python -c "
import MySQLdb
import os
try:
    MySQLdb.connect(
        host=os.environ.get('DB_HOST', 'mysql_db'),
        port=int(os.environ.get('DB_PORT', '3306')),
        user=os.environ.get('DB_USER', 'root'),
        passwd=os.environ.get('DB_PASSWORD', 'root'),
        db=os.environ.get('DB_NAME', 'techshop_db')
    )
    print('MySQL ready!')
    exit(0)
except Exception as e:
    print(f'Waiting for MySQL... attempt {$i}/30: {e}')
    exit(1)
" && break || sleep 3
done

# Chạy migrations
echo "Chạy Django migrations..."
python manage.py makemigrations shop --noinput 2>/dev/null || true
python manage.py migrate --noinput

# Seed dữ liệu mẫu
echo "Seed dữ liệu mẫu..."
python manage.py seed_data 2>/dev/null || true

# Tạo superuser nếu chưa có
echo "Tạo superuser admin..."
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@techshop.vn', 'admin123')
    print('Superuser created: admin / admin123')
else:
    print('Superuser already exists.')
" 2>/dev/null || true

echo "=== Khởi động Django server ==="
exec python manage.py runserver 0.0.0.0:8000
