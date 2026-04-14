import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'customer-service-secret-key-for-jwt'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'customer_app',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'customer_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'customer_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'customer_db'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'root'),
        'HOST': os.environ.get('DB_HOST', 'mysql_db'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}

CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'customer_app.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
}

JWT_SECRET_KEY = SECRET_KEY
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

def parse_product_service_map():
    """
    Parse PRODUCT_SERVICE_MAP from env.

    Format:
    product_type:service_path:base_url,product_type2:service_path2:base_url2
    Example:
    laptop:laptops:http://laptop-service:8000,mobile:mobiles:http://mobile-service:8000
    """
    raw = os.environ.get(
        'PRODUCT_SERVICE_MAP',
        (
            'laptop:laptops:http://laptop-service:8000,'
            'mobile:mobiles:http://mobile-service:8000,'
            'tablet:tablets:http://tablet-service:8000,'
            'accessory:accessories:http://accessory-service:8000,'
            'smartwatch:smartwatches:http://smartwatch-service:8000'
        )
    )

    mapping = {}
    for item in raw.split(','):
        item = item.strip()
        if not item:
            continue

        parts = item.split(':', 2)
        if len(parts) != 3:
            continue

        product_type = parts[0].strip().lower()
        service_path = parts[1].strip().lower()
        base_url = parts[2].strip().rstrip('/')

        if product_type and service_path and base_url:
            mapping[product_type] = {
                'service_path': service_path,
                'base_url': base_url,
            }

    return mapping


PRODUCT_SERVICES = parse_product_service_map()

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
