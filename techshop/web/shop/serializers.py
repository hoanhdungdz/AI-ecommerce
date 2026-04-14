from rest_framework import serializers
from .models import Category, Product, Order, OrderItem, ViewHistory


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'icon', 'product_count']

    def get_product_count(self, obj):
        return obj.products.count()


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'category', 'category_name', 'name', 'price',
            'stock', 'description', 'image_url', 'attributes',
            'created_at', 'updated_at'
        ]


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer nhẹ hơn cho danh sách sản phẩm."""
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'category_name', 'price', 'stock', 'image_url', 'attributes']


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'quantity', 'price_at_purchase', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'customer_id', 'total_amount', 'status', 'status_display',
            'shipping_address', 'note', 'items', 'created_at', 'updated_at'
        ]


class CreateOrderSerializer(serializers.Serializer):
    """Serializer cho tạo đơn hàng mới."""
    customer_id = serializers.IntegerField()
    shipping_address = serializers.CharField(required=False, default='')
    note = serializers.CharField(required=False, default='')
    items = serializers.ListField(
        child=serializers.DictField(),
        help_text="Danh sách: [{'product_id': 1, 'quantity': 2}, ...]"
    )


class ViewHistorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = ViewHistory
        fields = ['id', 'customer_id', 'product', 'product_name', 'viewed_at']
