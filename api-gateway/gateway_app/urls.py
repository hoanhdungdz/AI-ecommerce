from django.urls import path, re_path
from . import views

urlpatterns = [
    # Frontend pages
    path('', views.home_page, name='home'),
    path('customer/login/', views.customer_login_page, name='customer-login-page'),
    path('staff/login/', views.staff_login_page, name='staff-login-page'),

    # API proxy routes
    path('getfullapi/', views.get_full_api, name='get-full-api'),
    path('getfullapi', views.get_full_api, name='get-full-api-alt'),
    re_path(r'^api/(?P<service>[a-z][a-z0-9-]*)/(?P<path>.*)$', views.proxy_view, name='proxy'),
]
