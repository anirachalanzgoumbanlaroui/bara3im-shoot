from django.utils import timezone
from rest_framework import serializers

from apps.employees.models import Employee
from apps.employees.serializers import EmployeeSerializer

from .models import AttendanceMethod, AttendanceRule, AttendanceSession, AttendanceRecord, AttendanceLog

class AttendanceRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRule
        fields = [
            'id', 'attendance_method', 'work_start_time', 'grace_period_minutes', 'maximum_late_minutes',
            'late_deduction_amount', 'attendance_enabled', 'camera_enabled', 'camera_index',
            'camera_resolution', 'camera_fps', 'camera_auto_start', 'face_confidence_threshold',
            'face_recognition_enabled', 'allow_multiple_face_detection', 'recognition_cooldown_seconds',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class AttendanceSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceSession
        fields = '__all__'
        read_only_fields = ['id', 'token', 'generated_at', 'expiration_time', 'session_date', 'status', 'created_by', 'closed_at']

class AttendanceRecordSerializer(serializers.ModelSerializer):
    employee_details = EmployeeSerializer(source='employee', read_only=True)
    recorded_by_name = serializers.SerializerMethodField()
    audit_logs = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceRecord
        fields = [
            'id', 'employee', 'employee_details', 'date', 'check_in_time',
            'status', 'minutes_late', 'recorded_by', 'recorded_by_name', 'notes',
            'audit_logs', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'employee', 'employee_details', 'check_in_time', 'date', 'status',
            'minutes_late', 'recorded_by', 'recorded_by_name', 'audit_logs', 'created_at', 'updated_at'
        ]

    def get_recorded_by_name(self, obj):
        if not obj.recorded_by:
            return None
        full_name = f"{obj.recorded_by.first_name} {obj.recorded_by.last_name}".strip()
        return full_name or obj.recorded_by.get_username()

    def get_audit_logs(self, obj):
        logs = AttendanceLog.objects.filter(employee=obj.employee, timestamp__date=obj.date).order_by('-timestamp')
        return AttendanceLogSerializer(logs, many=True).data

class AttendanceRecordUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = ['status', 'minutes_late', 'notes']


class AttendanceManualCreateSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()
    notes = serializers.CharField()
    date = serializers.DateField(required=False)
    check_in_time = serializers.DateTimeField(required=False)


class AttendanceFingerprintPayloadSerializer(serializers.Serializer):
    fingerprint_sample = serializers.CharField(required=False, allow_blank=False)
    samples = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs):
        sample = attrs.get('fingerprint_sample')
        samples = attrs.get('samples')
        if not sample and not samples:
            raise serializers.ValidationError({'detail': 'A fingerprint sample is required.'})
        return attrs


class AttendanceIdentifySerializer(AttendanceFingerprintPayloadSerializer):
    pass


class AttendanceEnrollmentSerializer(AttendanceFingerprintPayloadSerializer):
    pass

class AttendanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceLog
        fields = ['id', 'employee', 'admin', 'action', 'description', 'timestamp']
        read_only_fields = fields

class ScanQRSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)
