from django.db import models
from django.db.models import JSONField


class Category(models.Model):
    """Danh mục sản phẩm: Laptop, Điện thoại, Quần áo, Phụ kiện,..."""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, default='package',
                            help_text="Emoji hoặc icon class")

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Model sản phẩm chung cho đa mặt hàng (EAV Pattern sử dụng JSONField).
    
    Trường `attributes` lưu các thông số đặc thù theo từng loại hàng:
    - Laptop: {"RAM": "16GB", "CPU": "Intel i7", "SSD": "512GB", "Brand": "Dell"}
    - Điện thoại: {"RAM": "8GB", "Screen": "6.7 inch", "Battery": "5000mAh"}
    - Quần áo: {"Size": "L", "Color": "Đen", "Material": "Cotton"}
    """
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, null=True,
                                help_text="URL hình ảnh sản phẩm")

    # === EAV / Dynamic Attributes using JSONField ===
    # Lưu các thông số kỹ thuật đặc thù theo loại hàng
    attributes = JSONField(default=dict, blank=True,
                           help_text="Thông số kỹ thuật dạng JSON, VD: {\"RAM\": \"8GB\"}")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.price:,.0f} VNĐ"

    @classmethod
    def filter_by_attributes(cls, **kwargs):
        """
        Lọc sản phẩm dựa trên các keys trong JSONField.
        
        Cách sử dụng:
            Product.filter_by_attributes(RAM="8GB", Brand="Dell")
        
        Sẽ được dịch thành Django ORM lookup:
            Product.objects.filter(attributes__RAM="8GB", attributes__Brand="Dell")
        """
        filter_kwargs = {f"attributes__{key}": value for key, value in kwargs.items()}
        return cls.objects.filter(**filter_kwargs)

    @classmethod
    def filter_by_attributes_advanced(cls, category_name=None, min_price=None,
                                       max_price=None, **attr_kwargs):
        """
        Lọc nâng cao: kết hợp Category, giá, và JSONField attributes.
        
        Cách sử dụng:
            Product.filter_by_attributes_advanced(
                category_name="Laptop",
                min_price=10000000,
                max_price=30000000,
                RAM="16GB"
            )
        """
        queryset = cls.objects.all()

        if category_name:
            queryset = queryset.filter(category__name__icontains=category_name)
        if min_price is not None:
            queryset = queryset.filter(price__gte=min_price)
        if max_price is not None:
            queryset = queryset.filter(price__lte=max_price)

        # Filter theo JSONField attributes
        for key, value in attr_kwargs.items():
            queryset = queryset.filter(**{f"attributes__{key}": value})

        return queryset

    @classmethod
    def search_products(cls, query):
        """Tìm kiếm sản phẩm theo tên hoặc mô tả."""
        return cls.objects.filter(
            models.Q(name__icontains=query) | models.Q(description__icontains=query)
        )


class Order(models.Model):
    """Đơn hàng của khách."""
    STATUS_CHOICES = [
        ('PENDING', 'Đang chờ'),
        ('PROCESSING', 'Đang xử lý'),
        ('COMPLETED', 'Hoàn thành'),
        ('CANCELLED', 'Đã hủy'),
    ]

    customer_id = models.IntegerField(help_text="ID của khách hàng từ Customer Service")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='PENDING')
    shipping_address = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} - Customer #{self.customer_id} - {self.get_status_display()}"

    def calculate_total(self):
        """Tính lại tổng tiền từ các OrderItem."""
        total = sum(item.price_at_purchase * item.quantity for item in self.items.all())
        self.total_amount = total
        self.save(update_fields=['total_amount'])
        return total


class OrderItem(models.Model):
    """Chi tiết đơn hàng — mỗi sản phẩm trong đơn."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price_at_purchase = models.DecimalField(max_digits=12, decimal_places=2,
                                            help_text="Giá tại thời điểm mua")

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return self.price_at_purchase * self.quantity


class ViewHistory(models.Model):
    """
    Lịch sử xem sản phẩm của khách hàng.
    Dùng để train Deep Learning model dự đoán hành vi mua hàng.
    """
    customer_id = models.IntegerField(help_text="ID của khách hàng")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='views')
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['viewed_at']

    def __str__(self):
        return f"Customer #{self.customer_id} viewed {self.product.name}"
