import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'api-gateway-secret-key'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'gateway_app',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'gateway_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'gateway_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

CORS_ALLOW_ALL_ORIGINS = True

# Service URLs
CUSTOMER_SERVICE_URL = os.environ.get('CUSTOMER_SERVICE_URL', 'http://customer-service:8000')
STAFF_SERVICE_URL = os.environ.get('STAFF_SERVICE_URL', 'http://staff-service:8000')


def parse_gateway_service_map():
    """
    Parse GATEWAY_SERVICE_MAP from env.

    Format:
    service_name:base_url,service_name2:base_url2
    Example:
    customers:http://customer-service:8000,staff:http://staff-service:8000,laptops:http://laptop-service:8000
    """
    default_map = (
        'customers:http://customer-service:8000,'
        'staff:http://staff-service:8000,'
        'laptops:http://laptop-service:8000,'
        'mobiles:http://mobile-service:8000,'
        'tablets:http://tablet-service:8000,'
        'accessories:http://accessory-service:8000,'
        'smartwatches:http://smartwatch-service:8000'
    )
    raw = os.environ.get('GATEWAY_SERVICE_MAP', default_map)

    mapping = {}
    for item in raw.split(','):
        item = item.strip()
        if not item:
            continue

        parts = item.split(':', 1)
        if len(parts) != 2:
            continue

        service_name = parts[0].strip().lower()
        base_url = parts[1].strip().rstrip('/')

        if service_name and base_url:
            mapping[service_name] = base_url

    return mapping


GATEWAY_SERVICE_MAP = parse_gateway_service_map()

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
