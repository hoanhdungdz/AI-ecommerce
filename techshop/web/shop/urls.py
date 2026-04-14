from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'orders', views.OrderViewSet, basename='order')
router.register(r'view-history', views.ViewHistoryViewSet, basename='viewhistory')

urlpatterns = [
    path('', include(router.urls)),

    # AI Service proxy endpoints
    path('ai/chat/', views.ai_chat, name='ai-chat'),
    path('ai/predict/', views.ai_predict, name='ai-predict'),
]
