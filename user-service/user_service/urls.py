"""
URL configuration for user_service project.

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
from app.views import AuthVerifyView, HealthView, LoginView, RoleLoginView, RoleRegisterView, RoleView, UserBehaviorView, UserRoleView, UserView

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('health/', HealthView.as_view(), name='health'),
    path('users/', UserView.as_view(), name='users'),
    path('roles/', RoleView.as_view(), name='roles'),
    path('user-roles/', UserRoleView.as_view(), name='user-roles'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/verify/', AuthVerifyView.as_view(), name='auth-verify'),
    path('behaviors/', UserBehaviorView.as_view(), name='behaviors'),
    path('customer/register/', RoleRegisterView.as_view(), {'role_name': 'CUSTOMER'}, name='customer-register'),
    path('customer/login/', RoleLoginView.as_view(), {'role_name': 'CUSTOMER'}, name='customer-login'),
    path('staff/register/', RoleRegisterView.as_view(), {'role_name': 'STAFF'}, name='staff-register'),
    path('staff/login/', RoleLoginView.as_view(), {'role_name': 'STAFF'}, name='staff-login'),
    path('admin/register/', RoleRegisterView.as_view(), {'role_name': 'ADMIN'}, name='admin-register'),
    path('admin/login/', RoleLoginView.as_view(), {'role_name': 'ADMIN'}, name='admin-login'),
]
