import jwt
import hashlib
import datetime
import requests
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Customer, Cart, CartItem, Order, OrderItem
from .serializers import (
    CustomerSerializer, CustomerRegisterSerializer,
    CartSerializer, CartItemSerializer, OrderSerializer
)


def _get_product_service(product_type):
    return settings.PRODUCT_SERVICES.get(str(product_type).lower())


def _product_detail_url(product_type, product_id):
    service = _get_product_service(product_type)
    if not service:
        return None
    return f"{service['base_url']}/api/{service['service_path']}/{product_id}/"


def _product_stock_action_url(product_type, product_id, action):
    service = _get_product_service(product_type)
    if not service:
        return None
    return f"{service['base_url']}/api/{service['service_path']}/{product_id}/{action}/"


def _product_search_url(product_type):
    service = _get_product_service(product_type)
    if not service:
        return None
    return f"{service['base_url']}/api/{service['service_path']}/search/"


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token(customer):
    payload = {
        'id': customer.id,
        'username': customer.username,
        'type': 'customer',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=settings.JWT_EXPIRATION_HOURS),
        'iat': datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


@api_view(['POST'])
def register(request):
    serializer = CustomerRegisterSerializer(data=request.data)
    if serializer.is_valid():
        customer = Customer.objects.create(
            username=serializer.validated_data['username'],
            password=hash_password(serializer.validated_data['password']),
            email=serializer.validated_data['email'],
            full_name=serializer.validated_data.get('full_name', ''),
            phone=serializer.validated_data.get('phone', ''),
        )
        token = generate_token(customer)
        return Response({
            'message': 'Đăng ký thành công!',
            'token': token,
            'customer': CustomerSerializer(customer).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    try:
        customer = Customer.objects.get(username=username)
        if customer.password == hash_password(password):
            token = generate_token(customer)
            return Response({
                'message': 'Đăng nhập thành công!',
                'token': token,
                'customer': CustomerSerializer(customer).data
            })
        return Response({'error': 'Sai mật khẩu!'}, status=status.HTTP_401_UNAUTHORIZED)
    except Customer.DoesNotExist:
        return Response({'error': 'Tài khoản không tồn tại!'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_cart(request):
    cart = Cart.objects.create(customer=request.user)
    return Response({
        'message': 'Tạo giỏ hàng thành công!',
        'cart': CartSerializer(cart).data
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_cart(request):
    carts = Cart.objects.filter(customer=request.user).order_by('-created_at')
    serializer = CartSerializer(carts, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_cart(request):
    cart_id = request.data.get('cart_id')
    product_id = request.data.get('product_id')
    product_type = request.data.get('product_type')
    quantity = request.data.get('quantity', 1)

    try:
        cart = Cart.objects.get(id=cart_id, customer=request.user)
    except Cart.DoesNotExist:
        return Response({'error': 'Giỏ hàng không tồn tại!'}, status=status.HTTP_404_NOT_FOUND)

    service_url = _product_detail_url(product_type, product_id)
    if not service_url:
        return Response({'error': 'Loại sản phẩm không hợp lệ!'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        resp = requests.get(service_url, timeout=5)
        if resp.status_code != 200:
            return Response({'error': 'Sản phẩm không tồn tại!'}, status=status.HTTP_404_NOT_FOUND)
        product = resp.json()
    except requests.exceptions.RequestException:
        return Response({'error': 'Không thể kết nối tới service sản phẩm!'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Check if item already in cart
    existing_item = CartItem.objects.filter(cart=cart, product_id=product_id, product_type=product_type).first()
    if existing_item:
        existing_item.quantity += int(quantity)
        existing_item.save()
        item = existing_item
    else:
        item = CartItem.objects.create(
            cart=cart,
            product_id=product_id,
            product_type=product_type,
            product_name=product['name'],
            product_price=product['price'],
            quantity=int(quantity),
        )

    return Response({
        'message': 'Đã thêm vào giỏ hàng!',
        'item': CartItemSerializer(item).data
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_cart(request, item_id):
    try:
        # Check if the item belongs to a cart owned by the current customer
        item = CartItem.objects.get(id=item_id, cart__customer=request.user)
        item.delete()
        return Response({'message': 'Đã xóa sản phẩm khỏi giỏ hàng!'})
    except CartItem.DoesNotExist:
        return Response({'error': 'Sản phẩm không tồn tại trong giỏ hàng!'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_cart(request, cart_id):
    try:
        cart = Cart.objects.get(id=cart_id, customer=request.user)
        cart.delete()
        return Response({'message': 'Đã xóa giỏ hàng thành công!'})
    except Cart.DoesNotExist:
        return Response({'error': 'Giỏ hàng không tồn tại!'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def checkout_cart(request, cart_id):
    try:
        cart = Cart.objects.get(id=cart_id, customer=request.user)
    except Cart.DoesNotExist:
        return Response({'error': 'Giỏ hàng không tồn tại!'}, status=status.HTTP_404_NOT_FOUND)

    items = cart.items.all()
    if not items:
        return Response({'error': 'Giỏ hàng trống!'}, status=status.HTTP_400_BAD_REQUEST)

    successful_deductions = []
    
    # 1. Deduct stock for all items
    for item in items:
        deduct_url = _product_stock_action_url(item.product_type, item.product_id, 'deduct_stock')
        if not deduct_url:
            _rollback_stock(successful_deductions)
            return Response(
                {'error': f'Loại sản phẩm không được hỗ trợ: {item.product_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            resp = requests.post(deduct_url, json={'quantity': item.quantity}, timeout=5)
            if resp.status_code == 200:
                successful_deductions.append({
                    'product_type': item.product_type,
                    'product_id': item.product_id,
                    'quantity': item.quantity,
                    'rollback_url': _product_stock_action_url(item.product_type, item.product_id, 'return_stock')
                })
            else:
                # Rollback previous deductions if one fails
                error_msg = resp.json().get('error', 'Lỗi không xác định khi trừ kho')
                _rollback_stock(successful_deductions)
                return Response({'error': f'Thanh toán thất bại: {item.product_name} - {error_msg}'}, status=status.HTTP_400_BAD_REQUEST)
        except requests.exceptions.RequestException:
            _rollback_stock(successful_deductions)
            return Response({'error': f'Không thể kết nối tới service kho hàng cho {item.product_name}'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # 2. Create Order
    try:
        address = request.data.get('address', '')
        method = request.data.get('method', 'cod')
        
        total_amount = sum(item.product_price * item.quantity for item in items)
        
        order = Order.objects.create(
            customer=request.user,
            address=address,
            payment_method=method,
            total_amount=total_amount
        )
        
        for item in items:
            OrderItem.objects.create(
                order=order,
                product_id=item.product_id,
                product_type=item.product_type,
                product_name=item.product_name,
                product_price=item.product_price,
                quantity=item.quantity
            )
            
        # 3. Clear cart (delete cart)
        cart.delete()
        
        return Response({'message': 'Thanh toán thành công! Mã đơn của bạn đã được ghi nhận.'})
    except Exception as e:
        # Rollback stock if order creation fails
        _rollback_stock(successful_deductions)
        return Response({'error': f'Lỗi hệ thống khi tạo đơn hàng: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _rollback_stock(deductions):
    """Gửi yêu cầu hoàn kho cho các sản phẩm đã trừ thành công."""
    for d in deductions:
        try:
            requests.post(d['rollback_url'], json={'quantity': d['quantity']}, timeout=5)
        except:
            # log failure in real system
            pass


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_orders(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def search_products(request):
    query = request.query_params.get('q', '')
    results = {product_type: [] for product_type in settings.PRODUCT_SERVICES.keys()}

    for product_type in settings.PRODUCT_SERVICES.keys():
        search_url = _product_search_url(product_type)
        if not search_url:
            continue
        try:
            resp = requests.get(search_url, params={'q': query}, timeout=5)
            if resp.status_code == 200:
                results[product_type] = resp.json()
        except requests.exceptions.RequestException:
            continue

    return Response(results)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    return Response(CustomerSerializer(request.user).data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    customer = request.user
    if 'full_name' in request.data:
        customer.full_name = request.data['full_name']
    if 'email' in request.data:
        customer.email = request.data['email']
    if 'phone' in request.data:
        customer.phone = request.data['phone']
    if 'password' in request.data and request.data['password']:
        customer.password = hash_password(request.data['password'])
    customer.save()
    return Response({
        'message': 'Cập nhật thông tin thành công!',
        'customer': CustomerSerializer(customer).data
    })
