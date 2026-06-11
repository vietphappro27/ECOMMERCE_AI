"""
URL configuration for product_service project.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from app.viewsets import CategoryViewSet, ProductViewSet
from app.views import HealthView

# DRF router for API endpoints
router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', HealthView.as_view(), name='health'),
    path('', include(router.urls)),
]
