"""
Management Command: Seed dữ liệu mẫu cho TechShop.
Chạy bằng: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from shop.models import Category, Product, Order, OrderItem, ViewHistory


class Command(BaseCommand):
    help = 'Seed dữ liệu mẫu cho TechShop (Category, Product, Order, ViewHistory)'

    def handle(self, *args, **options):
        if Product.objects.exists():
            self.stdout.write(self.style.WARNING('Dữ liệu đã tồn tại, bỏ qua seed.'))
            return

        self.stdout.write('Đang tạo dữ liệu mẫu...')

        # ===== CATEGORIES =====
        cat_laptop, _ = Category.objects.get_or_create(name='Laptop', defaults={'description': 'Máy tính xách tay các loại', 'icon': 'laptop'})
        cat_phone, _ = Category.objects.get_or_create(name='Điện thoại', defaults={'description': 'Smartphone và phụ kiện', 'icon': 'phone'})
        cat_accessory, _ = Category.objects.get_or_create(name='Phụ kiện', defaults={'description': 'Tai nghe, chuột, bàn phím,...', 'icon': 'accessory'})

        # ===== PRODUCTS - LAPTOP =====
        p1 = Product.objects.create(
            category=cat_laptop, name='Dell XPS 15',
            price=35000000, stock=10,
            description='Laptop cao cấp, mỏng nhẹ, phù hợp lập trình và đồ hoạ.',
            image_url='https://via.placeholder.com/400x300?text=Dell+XPS+15',
            attributes={"RAM": "16GB", "CPU": "Intel Core i7-13700H", "SSD": "512GB",
                        "Screen": "15.6 inch OLED", "Brand": "Dell", "Weight": "1.86kg"}
        )
        p2 = Product.objects.create(
            category=cat_laptop, name='MacBook Pro 14 M3',
            price=52000000, stock=5,
            description='MacBook Pro chip M3, hiệu năng vượt trội cho developer.',
            image_url='https://via.placeholder.com/400x300?text=MacBook+Pro+14',
            attributes={"RAM": "18GB", "CPU": "Apple M3 Pro", "SSD": "512GB",
                        "Screen": "14.2 inch Liquid Retina XDR", "Brand": "Apple", "Weight": "1.55kg"}
        )
        p3 = Product.objects.create(
            category=cat_laptop, name='ASUS ROG Strix G16',
            price=28000000, stock=15,
            description='Laptop gaming mạnh mẽ với GPU RTX 4060.',
            image_url='https://via.placeholder.com/400x300?text=ASUS+ROG+Strix',
            attributes={"RAM": "16GB", "CPU": "Intel Core i7-13650HX", "SSD": "512GB",
                        "GPU": "RTX 4060", "Screen": "16 inch 165Hz", "Brand": "ASUS", "Weight": "2.5kg"}
        )
        p4 = Product.objects.create(
            category=cat_laptop, name='Lenovo ThinkPad X1 Carbon',
            price=32000000, stock=8,
            description='Laptop doanh nhân, bền bỉ, bàn phím tốt nhất.',
            image_url='https://via.placeholder.com/400x300?text=ThinkPad+X1',
            attributes={"RAM": "16GB", "CPU": "Intel Core i7-1365U", "SSD": "512GB",
                        "Screen": "14 inch 2.8K", "Brand": "Lenovo", "Weight": "1.12kg"}
        )
        p5 = Product.objects.create(
            category=cat_laptop, name='HP Pavilion 15',
            price=15000000, stock=20,
            description='Laptop phổ thông, giá rẻ, phù hợp sinh viên.',
            image_url='https://via.placeholder.com/400x300?text=HP+Pavilion+15',
            attributes={"RAM": "8GB", "CPU": "Intel Core i5-1335U", "SSD": "256GB",
                        "Screen": "15.6 inch FHD", "Brand": "HP", "Weight": "1.75kg"}
        )

        # ===== PRODUCTS - ĐIỆN THOẠI =====
        p6 = Product.objects.create(
            category=cat_phone, name='iPhone 15 Pro Max',
            price=34990000, stock=12,
            description='Flagship Apple, camera 48MP, chip A17 Pro.',
            image_url='https://via.placeholder.com/400x300?text=iPhone+15+Pro+Max',
            attributes={"RAM": "8GB", "CPU": "A17 Pro", "Storage": "256GB",
                        "Screen": "6.7 inch Super Retina XDR", "Battery": "4441mAh",
                        "Brand": "Apple", "Color": "Titan Tự nhiên"}
        )
        p7 = Product.objects.create(
            category=cat_phone, name='Samsung Galaxy S24 Ultra',
            price=31990000, stock=10,
            description='Flagship Samsung, camera 200MP, S-Pen tích hợp.',
            image_url='https://via.placeholder.com/400x300?text=Galaxy+S24+Ultra',
            attributes={"RAM": "12GB", "CPU": "Snapdragon 8 Gen 3", "Storage": "256GB",
                        "Screen": "6.8 inch Dynamic AMOLED 2X", "Battery": "5000mAh",
                        "Brand": "Samsung", "Color": "Titan Gray"}
        )
        p8 = Product.objects.create(
            category=cat_phone, name='Xiaomi 14',
            price=12990000, stock=25,
            description='Flagship killer Xiaomi, camera Leica, giá tốt.',
            image_url='https://via.placeholder.com/400x300?text=Xiaomi+14',
            attributes={"RAM": "12GB", "CPU": "Snapdragon 8 Gen 3", "Storage": "256GB",
                        "Screen": "6.36 inch LTPO AMOLED", "Battery": "4610mAh",
                        "Brand": "Xiaomi", "Color": "Đen"}
        )

        # ===== PRODUCTS - PHỤ KIỆN =====
        p9 = Product.objects.create(
            category=cat_accessory, name='Tai nghe Sony WH-1000XM5',
            price=7500000, stock=30,
            description='Tai nghe chống ồn hàng đầu, âm thanh Hi-Res.',
            image_url='https://via.placeholder.com/400x300?text=Sony+WH1000XM5',
            attributes={"Type": "Over-ear", "Connectivity": "Bluetooth 5.3",
                        "ANC": "Có", "Battery": "30 giờ", "Brand": "Sony"}
        )
        p10 = Product.objects.create(
            category=cat_accessory, name='Chuột Logitech MX Master 3S',
            price=2490000, stock=40,
            description='Chuột không dây cao cấp cho lập trình viên.',
            image_url='https://via.placeholder.com/400x300?text=MX+Master+3S',
            attributes={"Type": "Wireless", "DPI": "8000", "Battery": "70 ngày",
                        "Brand": "Logitech", "Connectivity": "Bluetooth + USB-C"}
        )

        # ===== ORDERS (Mẫu) =====
        order1 = Order.objects.create(customer_id=1, status='COMPLETED', shipping_address='123 Nguyễn Huệ, Q.1, TP.HCM')
        OrderItem.objects.create(order=order1, product=p1, quantity=1, price_at_purchase=p1.price)
        OrderItem.objects.create(order=order1, product=p9, quantity=1, price_at_purchase=p9.price)
        order1.calculate_total()

        order2 = Order.objects.create(customer_id=2, status='PENDING', shipping_address='456 Lê Lợi, Q.3, TP.HCM')
        OrderItem.objects.create(order=order2, product=p6, quantity=1, price_at_purchase=p6.price)
        OrderItem.objects.create(order=order2, product=p10, quantity=1, price_at_purchase=p10.price)
        order2.calculate_total()

        # ===== VIEW HISTORY (Mẫu cho Deep Learning) =====
        # Giả lập Customer #1 xem nhiều laptop
        for product in [p1, p3, p2, p4, p5, p1, p2]:
            ViewHistory.objects.create(customer_id=1, product=product)

        # Customer #2 xem điện thoại + phụ kiện
        for product in [p6, p7, p8, p9, p10, p6]:
            ViewHistory.objects.create(customer_id=2, product=product)

        # Customer #3 xem đa dạng
        for product in [p5, p10, p8, p1, p9]:
            ViewHistory.objects.create(customer_id=3, product=product)

        self.stdout.write(self.style.SUCCESS(
            f'✅ Seed thành công: {Category.objects.count()} categories, '
            f'{Product.objects.count()} products, {Order.objects.count()} orders, '
            f'{ViewHistory.objects.count()} view histories'
        ))
