"""
URL configuration for cart_service project.

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
from app.views import CartItemDetailView, CartItemView, CartView, HealthView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', HealthView.as_view(), name='health'),
    path('carts/', CartView.as_view(), name='carts'),
    path('cart-items/', CartItemView.as_view(), name='cart-items'),
    path('cart-items/<int:item_id>/', CartItemDetailView.as_view(), name='cart-item-detail'),
]
