from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='auth-login'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('me/', views.MeView.as_view(), name='auth-me'),
    path('change-password/', views.ChangePasswordView.as_view(), name='auth-change-password'),
    path('refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
]
