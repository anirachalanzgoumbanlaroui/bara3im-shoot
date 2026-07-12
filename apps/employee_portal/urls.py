from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeDashboardViewSet

app_name = 'employee_portal'

router = DefaultRouter()
router.register(r'', EmployeeDashboardViewSet, basename='employee-portal')

urlpatterns = [
    path('', include(router.urls)),
]
