from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='customer-register'),
    path('login/', views.login, name='customer-login'),
    path('profile/', views.get_profile, name='get-profile'),
    path('profile/update/', views.update_profile, name='update-profile'),
    path('cart/create/', views.create_cart, name='create-cart'),
    path('cart/', views.get_cart, name='get-cart'),
    path('cart/add/', views.add_to_cart, name='add-to-cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove-from-cart'),
    path('cart/delete/<int:cart_id>/', views.delete_cart, name='delete-cart'),
    path('cart/checkout/<int:cart_id>/', views.checkout_cart, name='checkout-cart'),
    path('orders/', views.get_orders, name='get-orders'),
    path('search/', views.search_products, name='search-products'),
]
