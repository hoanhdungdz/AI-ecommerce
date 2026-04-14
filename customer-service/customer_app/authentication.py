import jwt
from django.conf import settings
from rest_framework import authentication, exceptions
from .models import Customer

class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token đã hết hạn')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Token không hợp lệ')

        try:
            user = Customer.objects.get(id=payload['id'])
        except Customer.DoesNotExist:
            raise exceptions.AuthenticationFailed('Không tìm thấy người dùng')

        return (user, None)
