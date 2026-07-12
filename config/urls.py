"""
URL configuration for Bara3im Shoot project.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/', include('common.urls')),
    path('api/', include('apps.employees.urls')),
    path('api/', include('apps.daily_sessions.urls')),
    path('api/attendance/', include('apps.attendance.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/employee-portal/', include('apps.employee_portal.urls')),
]
