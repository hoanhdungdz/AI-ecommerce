import logging
import re
import requests
from django.conf import settings
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response

from .models import Category, Product, Order, OrderItem, ViewHistory
from .serializers import (
    CategorySerializer, ProductSerializer, ProductListSerializer,
    OrderSerializer, CreateOrderSerializer,
    OrderItemSerializer, ViewHistorySerializer
)

logger = logging.getLogger(__name__)

# URL của AI Service (trong Docker network)
AI_SERVICE_URL = settings.AI_SERVICE_URL
AI_REQUEST_TIMEOUT = 120


def _strip_accents(text):
    import unicodedata
    if not text:
        return ""
    text = str(text).replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _extract_budget_constraints(query):
    q = _strip_accents((query or "").lower())
    constraints = {"min_price": None, "max_price": None}

    range_m = re.search(
        r"(?:tu\s+)?(\d+(?:[\.,]\d+)?)\s*(trieu|tr|m|nghin|k)?\s*(?:-|den|toi|toi)\s*(\d+(?:[\.,]\d+)?)\s*(trieu|tr|m|nghin|k)?",
        q
    )
    if range_m:
        def unit_mul(u):
            return 1_000_000 if u in {"trieu", "tr", "m"} else 1_000 if u in {"nghin", "k"} else 1

        low = float(range_m.group(1).replace(",", ".")) * unit_mul((range_m.group(2) or "").strip())
        high = float(range_m.group(3).replace(",", ".")) * unit_mul((range_m.group(4) or "").strip())
        constraints["min_price"] = min(low, high)
        constraints["max_price"] = max(low, high)
        return constraints

    m = re.search(r"(\d+(?:[\.,]\d+)?)\s*(trieu|tr|m|nghin|k)?", q)
    if not m:
        return constraints

    val = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "").strip()
    mul = 1_000_000 if unit in {"trieu", "tr", "m"} else 1_000 if unit in {"nghin", "k"} else 1
    price = val * mul

    if re.search(r"(duoi|nho hon|<=|<|re nhat|gia re|tiet kiem)", q):
        constraints["max_price"] = price
    elif re.search(r"(tren|lon hon|>=|>)", q):
        constraints["min_price"] = price
    elif re.search(r"(tam|khoang|quanh|co)", q):
        constraints["min_price"] = price * 0.8
        constraints["max_price"] = price * 1.2

    return constraints


def _extract_chat_constraints(query):
    """
    Step 1 - Extractor:
    Trả về JSON chuẩn theo yêu cầu bài toán:
    {
      "category": "laptop/mobile/...",
      "min_price": int|None,
      "max_price": int|None,
      "brands": [],
      "specific_models": []
    }
    """
    q = _strip_accents((query or "").lower())
    budget = _extract_budget_constraints(query)

    category = None
    category_map = [
        ("laptop", ["laptop", "notebook"]),
        ("mobile", ["dien thoai", "mobile", "smartphone", "phone"]),
        ("tablet", ["tablet", "may tinh bang"]),
        ("smartwatch", ["smartwatch", "dong ho thong minh", "watch"]),
        ("accessory", ["phu kien", "accessory", "accessories"]),
    ]
    for cat, keys in category_map:
        if any(k in q for k in keys):
            category = cat
            break

    known_brands = [
        "apple", "asus", "acer", "lenovo", "dell", "hp", "msi", "samsung",
        "xiaomi", "huawei", "garmin", "oppo", "sony", "google"
    ]
    brands = [b for b in known_brands if re.search(rf"\b{re.escape(b)}\b", q)]

    # Các tên mẫu để detect compare cụ thể theo yêu cầu đồ án.
    compare_aliases = {
        "macbook": ["macbook"],
        "asus": ["asus"],
        "thinkpad": ["thinkpad"],
        "x1 carbon": ["x1 carbon"],
        "rog": ["rog"],
        "swift": ["swift"],
        "dell xps": ["dell xps", "xps"],
        "iphone": ["iphone"],
        "galaxy": ["galaxy"],
    }
    specific_models = [name for name, keys in compare_aliases.items() if any(k in q for k in keys)]

    return {
        "category": category,
        "min_price": budget["min_price"],
        "max_price": budget["max_price"],
        "brands": brands,
        "specific_models": specific_models,
    }


def _build_hard_filtered_queryset(query):
    """
    Step 2 - Executor:
    Dùng JSON từ extractor để lọc ORM chính xác trước khi gửi context cho AI.
    """
    constraints = _extract_chat_constraints(query)
    qs = Product.objects.select_related("category").all()

    if constraints.get("category"):
        qs = qs.filter(category__name__icontains=constraints["category"])

    if constraints.get("brands"):
        brand_q = Q()
        for b in constraints["brands"]:
            brand_q |= Q(name__icontains=b) | Q(attributes__Brand__icontains=b)
        qs = qs.filter(brand_q)

    if constraints.get("min_price") is not None:
        qs = qs.filter(price__gte=constraints["min_price"])
    if constraints.get("max_price") is not None:
        qs = qs.filter(price__lte=constraints["max_price"])

    if constraints.get("specific_models"):
        cmp_q = Q()
        for term in constraints["specific_models"]:
            cmp_q |= Q(name__icontains=term)
        qs = qs.filter(cmp_q)

    return qs[:30], constraints


# =============================================
# Category API
# =============================================
class CategoryViewSet(viewsets.ModelViewSet):
    """CRUD API cho danh mục sản phẩm."""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


# =============================================
# Product API
# =============================================
class ProductViewSet(viewsets.ModelViewSet):
    """CRUD API cho sản phẩm."""
    queryset = Product.objects.select_related('category').all()

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    @action(detail=False, methods=['get'], url_path='filter')
    def filter_by_attrs(self, request):
        """
        Lọc sản phẩm theo JSONField attributes.
        
        VD: GET /api/products/filter/?RAM=8GB&Brand=Dell&category=Laptop&min_price=10000000
        """
        params = request.query_params.dict()

        category_name = params.pop('category', None)
        min_price = params.pop('min_price', None)
        max_price = params.pop('max_price', None)

        # Chuyển sang float nếu có
        if min_price:
            min_price = float(min_price)
        if max_price:
            max_price = float(max_price)

        products = Product.filter_by_attributes_advanced(
            category_name=category_name,
            min_price=min_price,
            max_price=max_price,
            **params
        )

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """
        Tìm kiếm sản phẩm theo tên/mô tả.
        VD: GET /api/products/search/?q=laptop+gaming
        """
        query = request.query_params.get('q', '')
        if not query:
            return Response({"error": "Vui lòng cung cấp từ khóa tìm kiếm (?q=...)"}, 
                          status=status.HTTP_400_BAD_REQUEST)

        products = Product.search_products(query)
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)


# =============================================
# Order API
# =============================================
class OrderViewSet(viewsets.ModelViewSet):
    """API cho đơn hàng."""
    queryset = Order.objects.prefetch_related('items__product').all()
    serializer_class = OrderSerializer

    def create(self, request, *args, **kwargs):
        """Tạo đơn hàng mới với danh sách sản phẩm."""
        ser = CreateOrderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Tạo Order
        order = Order.objects.create(
            customer_id=data['customer_id'],
            shipping_address=data.get('shipping_address', ''),
            note=data.get('note', ''),
        )

        # Tạo OrderItems
        for item_data in data['items']:
            try:
                product = Product.objects.get(id=item_data['product_id'])
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item_data.get('quantity', 1),
                    price_at_purchase=product.price,
                )
            except Product.DoesNotExist:
                logger.warning(f"Product {item_data['product_id']} not found, skipping.")

        # Tính tổng tiền
        order.calculate_total()

        result = OrderSerializer(order).data
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='by-customer/(?P<customer_id>[0-9]+)')
    def by_customer(self, request, customer_id=None):
        """Lấy đơn hàng theo customer_id."""
        orders = self.queryset.filter(customer_id=customer_id)
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)


# =============================================
# View History API
# =============================================
class ViewHistoryViewSet(viewsets.ModelViewSet):
    """API cho lịch sử xem sản phẩm."""
    queryset = ViewHistory.objects.select_related('product').all()
    serializer_class = ViewHistorySerializer

    @action(detail=False, methods=['get'], url_path='by-customer/(?P<customer_id>[0-9]+)')
    def by_customer(self, request, customer_id=None):
        """Lấy lịch sử xem theo customer_id."""
        history = self.queryset.filter(customer_id=customer_id)
        serializer = self.get_serializer(history, many=True)
        return Response(serializer.data)


# =============================================
# AI Integration Endpoints
# =============================================
@api_view(['GET'])
def ai_chat(request):
    """
    Proxy API gọi tới AI Service RAG Chatbot.
    VD: GET /api/ai/chat/?query=tôi muốn mua laptop gaming
    """
    query = request.query_params.get('query', '')
    if not query:
        return Response({"error": "Vui lòng nhập câu hỏi (?query=...)"}, 
                      status=status.HTTP_400_BAD_REQUEST)
    try:
        filtered_qs, constraints = _build_hard_filtered_queryset(query)

        context_products = []
        for p in filtered_qs:
            brand = ""
            if isinstance(p.attributes, dict):
                brand = str(p.attributes.get("Brand") or p.attributes.get("brand") or "")
            context_products.append({
                "id": p.id,
                "name": p.name,
                "category": p.category.name if p.category else "",
                "brand": brand,
                "price": float(p.price),
                "stock": p.stock,
                "description": p.description or "",
                "attributes": p.attributes or {},
            })

        resp = requests.post(
            f"{AI_SERVICE_URL}/api/chat/grounded",
            json={
                "query": query,
                "context_products": context_products,
                "constraints": constraints,
            },
            timeout=AI_REQUEST_TIMEOUT
        )
        try:
            payload = resp.json()
        except ValueError:
            payload = {"error": "AI Service trả về dữ liệu không hợp lệ"}

        if resp.status_code >= 400:
            return Response(payload, status=resp.status_code)

        return Response(payload)
    except requests.exceptions.RequestException as e:
        logger.error(f"AI Service error: {e}")
        return Response({"error": "AI Service không khả dụng"}, 
                      status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
def ai_predict(request):
    """
    Proxy API gọi tới AI Service Deep Learning Prediction.
    VD: GET /api/ai/predict/?history=10,15,20
    """
    history = request.query_params.get('history', '')
    if not history:
        return Response({"error": "Cung cấp lịch sử product IDs (?history=10,15,20)"}, 
                      status=status.HTTP_400_BAD_REQUEST)
    try:
        product_ids = [int(x.strip()) for x in history.split(',') if x.strip()]
    except ValueError:
        return Response({"error": "history phải là danh sách số nguyên, ví dụ: 10,15,20"},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        resp = requests.post(
            f"{AI_SERVICE_URL}/api/predict",
            json={"product_ids": product_ids},
            timeout=AI_REQUEST_TIMEOUT
        )
        try:
            payload = resp.json()
        except ValueError:
            payload = {"error": "AI Service trả về dữ liệu không hợp lệ"}

        if resp.status_code >= 400:
            return Response(payload, status=resp.status_code)

        return Response(payload)
    except requests.exceptions.RequestException as e:
        logger.error(f"AI Predict error: {e}")
        return Response({"error": "AI Service không khả dụng"}, 
                      status=status.HTTP_503_SERVICE_UNAVAILABLE)
