from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='staff-register'),
    path('login/', views.login, name='staff-login'),
    path('products/add/', views.add_product, name='add-product'),
    path('products/update/<int:product_id>/', views.update_product, name='update-product'),
]
