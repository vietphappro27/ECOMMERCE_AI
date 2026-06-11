"""
URL configuration for api_gateway project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from app.views import (
    AIChatProxyView,
    AIRecommendationProxyView,
    ApiRoleRegisterView,
    CustomerActivityProxyView,
    ApiRoleLoginView,
    CustomerCartProxyView,
    CustomerCartItemProxyView,
    CustomerCartPageView,
    CustomerDashboardView,
    CustomerLoginProxyView,
    CustomerRatingProxyView,
    CustomerRegisterProxyView,
    CustomerSearchProxyView,
    ProductCategoryProxyView,
    ProductProxyView,
    ProductDetailPageView,
    LoginPageView,
    LogoutView,
    OrderDetailProxyView,
    OrderProxyView,
    
    RegisterPageView,
    StaffDashboardView,
    StaffItemAttributesProxyView,
    StaffItemDetailProxyView,
    StaffItemProxyView,
    StaffLoginProxyView,
    StaffRegisterProxyView,
    UiLoginView,
    CustomerOrderPageView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', LoginPageView.as_view(), name='login-page'),
    path('ui/register/', RegisterPageView.as_view(), name='register-page'),
    path('ui/login/', UiLoginView.as_view(), name='ui-login'),
    path('ui/logout/', LogoutView.as_view(), name='ui-logout'),
    path('ui/customer/', CustomerDashboardView.as_view(), name='customer-dashboard'),
    path('ui/customer/product/<int:product_id>/', ProductDetailPageView.as_view(), name='product-detail-page'),
    path('ui/customer/cart/', CustomerCartPageView.as_view(), name='customer-cart-page'),
    path('ui/customer/orders/', CustomerOrderPageView.as_view(), name='customer-order-page'),
    path('ui/staff/', StaffDashboardView.as_view(), name='staff-dashboard'),
    path('api/auth/register/', ApiRoleRegisterView.as_view(), name='api-role-register'),
    path('api/auth/login/', ApiRoleLoginView.as_view(), name='api-role-login'),
    path('api/customer/register/', CustomerRegisterProxyView.as_view(), name='api-customer-register'),
    path('api/customer/login/', CustomerLoginProxyView.as_view(), name='api-customer-login'),
    path('api/customer/carts/', CustomerCartProxyView.as_view(), name='api-customer-carts'),
    path('api/customer/cart-items/', CustomerCartItemProxyView.as_view(), name='api-customer-cart-items'),
    path('api/customer/cart-items/<int:cart_item_id>/', CustomerCartItemProxyView.as_view(), name='api-customer-cart-item-detail'),
    path('api/customer/activities/', CustomerActivityProxyView.as_view(), name='api-customer-activities'),
    path('api/orders/', OrderProxyView.as_view(), name='api-orders'),
    path('api/orders/<int:order_id>/', OrderDetailProxyView.as_view(), name='api-order-detail'),
    path('api/customer/ratings/', CustomerRatingProxyView.as_view(), name='api-customer-ratings'),
    path('api/customer/search/', CustomerSearchProxyView.as_view(), name='api-customer-search'),
    path('api/ai/chat/', AIChatProxyView.as_view(), name='api-ai-chat'),
    path('api/ai/recommendations/<int:customer_id>/', AIRecommendationProxyView.as_view(), name='api-ai-recommendations'),
    path('api/staff/register/', StaffRegisterProxyView.as_view(), name='api-staff-register'),
    path('api/staff/login/', StaffLoginProxyView.as_view(), name='api-staff-login'),
    path('api/staff/items/', StaffItemProxyView.as_view(), name='api-staff-items'),
    path('api/staff/item-attributes/', StaffItemAttributesProxyView.as_view(), name='api-staff-item-attributes'),
    path('api/staff/items/<int:item_id>/', StaffItemDetailProxyView.as_view(), name='api-staff-item-detail'),
    path('api/categories/', ProductCategoryProxyView.as_view(), name='api-categories'),
    path('api/products/', ProductProxyView.as_view(), name='api-products'),
    path('api/products/<int:product_id>/', ProductProxyView.as_view(), name='api-product-detail'),
]
