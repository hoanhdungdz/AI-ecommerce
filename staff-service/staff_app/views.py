import jwt
import hashlib
import datetime
import requests
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Staff
from .serializers import StaffSerializer, StaffRegisterSerializer


def _get_product_service(product_type):
    return settings.PRODUCT_SERVICES.get(str(product_type).lower())


def _product_collection_url(product_type):
    service = _get_product_service(product_type)
    if not service:
        return None
    return f"{service['base_url']}/api/{service['service_path']}/"


def _product_detail_url(product_type, product_id):
    service = _get_product_service(product_type)
    if not service:
        return None
    return f"{service['base_url']}/api/{service['service_path']}/{product_id}/"


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token(staff):
    payload = {
        'id': staff.id,
        'username': staff.username,
        'type': 'staff',
        'role': staff.role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=settings.JWT_EXPIRATION_HOURS),
        'iat': datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


@api_view(['POST'])
def register(request):
    serializer = StaffRegisterSerializer(data=request.data)
    if serializer.is_valid():
        staff = Staff.objects.create(
            username=serializer.validated_data['username'],
            password=hash_password(serializer.validated_data['password']),
            email=serializer.validated_data['email'],
            full_name=serializer.validated_data.get('full_name', ''),
            role=serializer.validated_data.get('role', 'staff'),
        )
        token = generate_token(staff)
        return Response({
            'message': 'Đăng ký nhân viên thành công!',
            'token': token,
            'staff': StaffSerializer(staff).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    try:
        staff = Staff.objects.get(username=username)
        if staff.password == hash_password(password):
            token = generate_token(staff)
            return Response({
                'message': 'Đăng nhập thành công!',
                'token': token,
                'staff': StaffSerializer(staff).data
            })
        return Response({'error': 'Sai mật khẩu!'}, status=status.HTTP_401_UNAUTHORIZED)
    except Staff.DoesNotExist:
        return Response({'error': 'Tài khoản không tồn tại!'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def add_product(request):
    payload = verify_token(request)
    if not payload:
        return Response({'error': 'Chưa đăng nhập!'}, status=status.HTTP_401_UNAUTHORIZED)

    product_type = request.data.get('product_type')
    product_data = {
        'name': request.data.get('name'),
        'brand': request.data.get('brand'),
        'price': request.data.get('price'),
        'description': request.data.get('description', ''),
        'quantity': request.data.get('quantity', 0),
    }

    service_url = _product_collection_url(product_type)
    if not service_url:
        return Response({'error': 'Loại sản phẩm không hợp lệ!'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        resp = requests.post(service_url, json=product_data, timeout=5)
        if resp.status_code == 201:
            return Response({
                'message': 'Thêm sản phẩm thành công!',
                'product': resp.json()
            }, status=status.HTTP_201_CREATED)
        return Response(resp.json(), status=resp.status_code)
    except requests.exceptions.RequestException:
        return Response({'error': 'Không thể kết nối tới service sản phẩm!'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['PUT'])
def update_product(request, product_id):
    payload = verify_token(request)
    if not payload:
        return Response({'error': 'Chưa đăng nhập!'}, status=status.HTTP_401_UNAUTHORIZED)

    product_type = request.data.get('product_type')
    product_data = {}
    for field in ['name', 'brand', 'price', 'description', 'quantity']:
        if field in request.data:
            product_data[field] = request.data[field]

    service_url = _product_detail_url(product_type, product_id)
    if not service_url:
        return Response({'error': 'Loại sản phẩm không hợp lệ!'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        resp = requests.put(service_url, json=product_data, timeout=5)
        if resp.status_code == 200:
            return Response({
                'message': 'Cập nhật sản phẩm thành công!',
                'product': resp.json()
            })
        return Response(resp.json(), status=resp.status_code)
    except requests.exceptions.RequestException:
        return Response({'error': 'Không thể kết nối tới service sản phẩm!'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
