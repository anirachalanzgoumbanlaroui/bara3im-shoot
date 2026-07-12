from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet

app_name = 'notifications'

router = DefaultRouter()
router.register(r'my', NotificationViewSet, basename='my-notifications')

urlpatterns = [
    path('', include(router.urls)),
]
