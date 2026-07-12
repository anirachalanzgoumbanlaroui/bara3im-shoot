from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeViewSet, AttendanceLatePenaltyView

app_name = 'employees'

router = DefaultRouter()
router.register(r'employees', EmployeeViewSet, basename='employee')

urlpatterns = [
    path('', include(router.urls)),
    path(
        'attendance/<uuid:record_id>/late-penalty/',
        AttendanceLatePenaltyView.as_view(),
        name='attendance-late-penalty',
    ),
]
