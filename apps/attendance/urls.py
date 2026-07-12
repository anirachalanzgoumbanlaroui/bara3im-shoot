from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AttendanceAdminViewSet, AttendanceRecordViewSet, AttendanceEmployeeViewSet

router = DefaultRouter()
router.register(r'admin/records', AttendanceRecordViewSet, basename='admin-attendance-records')

urlpatterns = [
    # Admin APIs
    path('admin/dashboard/', AttendanceAdminViewSet.as_view({'get': 'dashboard'}), name='admin-dashboard'),
    path('admin/rules/', AttendanceAdminViewSet.as_view({'get': 'rules', 'put': 'rules'}), name='admin-rules'),
    path('admin/settings/', AttendanceAdminViewSet.as_view({'get': 'rules', 'put': 'rules'}), name='admin-settings'),
    path('admin/method/', AttendanceAdminViewSet.as_view({'get': 'attendance_method', 'put': 'attendance_method'}), name='admin-attendance-method'),
    path('admin/scanner/start/', AttendanceAdminViewSet.as_view({'post': 'start_scanning'}), name='admin-scanner-start'),
    path('admin/scanner/stop/', AttendanceAdminViewSet.as_view({'post': 'stop_scanning'}), name='admin-scanner-stop'),
    path('admin/scanner/status/', AttendanceAdminViewSet.as_view({'get': 'scanner_status'}), name='admin-scanner-status'),
    path('admin/fingerprint/identify/', AttendanceAdminViewSet.as_view({'post': 'identify_fingerprint'}), name='admin-fingerprint-identify'),
    path('admin/face/start/', AttendanceAdminViewSet.as_view({'post': 'start_face_recognition'}), name='admin-face-start'),
    path('admin/face/stop/', AttendanceAdminViewSet.as_view({'post': 'stop_face_recognition'}), name='admin-face-stop'),
    path('admin/face/status/', AttendanceAdminViewSet.as_view({'get': 'camera_status'}), name='admin-face-status'),
    path('admin/face/identify/', AttendanceAdminViewSet.as_view({'post': 'identify_face'}), name='admin-face-identify'),
    path('admin/manual/', AttendanceAdminViewSet.as_view({'post': 'manual_attendance'}), name='admin-manual-attendance'),
    path('admin/today/', AttendanceAdminViewSet.as_view({'get': 'today_attendance'}), name='admin-today-attendance'),
    path('admin/history/', AttendanceAdminViewSet.as_view({'get': 'history'}), name='admin-history'),
    path('admin/statistics/', AttendanceAdminViewSet.as_view({'get': 'statistics'}), name='admin-statistics'),

    # Compatibility aliases for the existing Flutter code during migration
    path('admin/session/open/', AttendanceAdminViewSet.as_view({'post': 'start_scanning'}), name='admin-session-open'),
    path('admin/session/close/', AttendanceAdminViewSet.as_view({'post': 'stop_scanning'}), name='admin-session-close'),
    path('admin/session/current/', AttendanceAdminViewSet.as_view({'get': 'scanner_status'}), name='admin-session-current'),
    path('admin/records-list/', AttendanceAdminViewSet.as_view({'get': 'history'}), name='admin-records-list'),
    
    # Employee APIs
    path('employee/scan/', AttendanceEmployeeViewSet.as_view({'post': 'scan'}), name='employee-scan'),
    path('employee/my/today/', AttendanceEmployeeViewSet.as_view({'get': 'today'}), name='employee-today'),
    path('employee/my/history/', AttendanceEmployeeViewSet.as_view({'get': 'history'}), name='employee-history'),
    path('employee/my/statistics/', AttendanceEmployeeViewSet.as_view({'get': 'statistics'}), name='employee-statistics'),
    
    path('', include(router.urls)),
]
