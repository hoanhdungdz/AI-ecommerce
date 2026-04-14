from django.contrib import admin
from .models import Customer, Cart, CartItem

admin.site.register(Customer)
admin.site.register(Cart)
admin.site.register(CartItem)
