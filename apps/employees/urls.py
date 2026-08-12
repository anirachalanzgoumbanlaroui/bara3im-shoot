from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeViewSet, AttendanceLatePenaltyView, AdminResetPasswordView

app_name = 'employees'

router = DefaultRouter()
router.register(r'employees', EmployeeViewSet, basename='employee')

urlpatterns = [
    path('', include(router.urls)),
    path(
        'admin/employees/<uuid:employee_id>/reset-password/',
        AdminResetPasswordView.as_view(),
        name='admin-employee-reset-password',
    ),
    path(
        'attendance/<uuid:record_id>/late-penalty/',
        AttendanceLatePenaltyView.as_view(),
        name='attendance-late-penalty',
    ),
]
