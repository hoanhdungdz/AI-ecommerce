from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import monitorViewSet

router = DefaultRouter()
router.register(r'', monitorViewSet)

urlpatterns = [
    path('', include(router.urls)),
]

