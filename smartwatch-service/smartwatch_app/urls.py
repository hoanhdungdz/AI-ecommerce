from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SmartwatchViewSet

router = DefaultRouter()
router.register(r'', SmartwatchViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
