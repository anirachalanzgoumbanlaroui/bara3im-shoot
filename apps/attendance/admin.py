from django.contrib import admin

from .models import AttendanceLog, AttendanceRecord, AttendanceRule, AttendanceSession


@admin.register(AttendanceRule)
class AttendanceRuleAdmin(admin.ModelAdmin):
	list_display = ('attendance_method', 'attendance_enabled', 'camera_enabled', 'face_recognition_enabled', 'updated_at')
	list_editable = ('attendance_enabled', 'camera_enabled', 'face_recognition_enabled')
	list_filter = ('attendance_method', 'attendance_enabled', 'camera_enabled', 'face_recognition_enabled')


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
	list_display = ('employee', 'date', 'status', 'check_in_time', 'recorded_by')
	list_filter = ('status', 'date')
	search_fields = ('employee__first_name', 'employee__last_name', 'employee__employee_code')


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
	list_display = ('session_date', 'status', 'generated_at', 'expiration_time')
	list_filter = ('status', 'session_date')


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
	list_display = ('action', 'employee', 'admin', 'timestamp')
	list_filter = ('action', 'timestamp')
