from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TabletViewSet

router = DefaultRouter()
router.register(r'', TabletViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
