from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, time

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.employees.models import Employee

from .models import AttendanceLog, AttendanceMethod, AttendanceRecord, AttendanceRule, AttendanceSession
from .serializers import (
    AttendanceEnrollmentSerializer,
    AttendanceFingerprintPayloadSerializer,
    AttendanceIdentifySerializer,
    AttendanceLogSerializer,
    AttendanceManualCreateSerializer,
    AttendanceRecordSerializer,
    AttendanceRecordUpdateSerializer,
    AttendanceRuleSerializer,
    ScanQRSerializer,
)
from .services.face.service import face_recognition_service
from .services.fingerprint.service import fingerprint_service
from .services.service import attendance_service

User = get_user_model()

class IsAdminUserOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class AttendancePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _get_rule_or_default():
    rule = AttendanceRule.get_active_rule()
    if rule:
        return rule
    return AttendanceRule.objects.create(work_start_time='09:00:00')


def _make_aware_for_today(today, value):
    if timezone.is_aware(value):
        return value
    current_tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(today, value), current_tz)


def _calculate_status(now, rule):
    start_datetime = _make_aware_for_today(now.date(), rule.work_start_time)
    grace_end = start_datetime + timedelta(minutes=rule.grace_period_minutes)
    maximum_late_end = start_datetime + timedelta(minutes=rule.maximum_late_minutes)

    if now <= grace_end:
        return AttendanceRecord.Status.PRESENT, 0

    minutes_late = int((now - start_datetime).total_seconds() / 60)
    if now <= maximum_late_end:
        return AttendanceRecord.Status.LATE, minutes_late

    return AttendanceRecord.Status.ABSENT, minutes_late


def _attendance_queryset_base():
    return AttendanceRecord.objects.select_related('employee', 'employee__user', 'recorded_by').all()


def _recent_activity():
    logs = AttendanceLog.objects.select_related('employee', 'admin').order_by('-timestamp')[:10]
    return AttendanceLogSerializer(logs, many=True).data


def _build_trend(days=7):
    today = timezone.localdate()
    trend = []
    for offset in range(days - 1, -1, -1):
        date_value = today - timedelta(days=offset)
        records = AttendanceRecord.objects.filter(date=date_value)
        trend.append({
            'date': date_value.isoformat(),
            'present_count': records.filter(status=AttendanceRecord.Status.PRESENT).count(),
            'late_count': records.filter(status=AttendanceRecord.Status.LATE).count(),
            'absent_count': records.filter(status=AttendanceRecord.Status.ABSENT).count(),
        })
    return trend


def _attendance_summary(today=None):
    today = today or timezone.localdate()
    records = AttendanceRecord.objects.filter(date=today)
    total_employees = Employee.objects.filter(status=Employee.Status.ACTIVE).count()

    present_count = records.filter(status=AttendanceRecord.Status.PRESENT).count()
    late_count = records.filter(status=AttendanceRecord.Status.LATE).count()
    absent_count = records.filter(status=AttendanceRecord.Status.ABSENT).count()

    attendance_rate = round(((present_count + late_count) / total_employees) * 100, 2) if total_employees else 0

    minutes_since_midnight = []
    for record in records.exclude(status=AttendanceRecord.Status.ABSENT):
        local_time = timezone.localtime(record.check_in_time).time()
        minutes_since_midnight.append(local_time.hour * 60 + local_time.minute + (local_time.second / 60))

    average_arrival_time = None
    if minutes_since_midnight:
        average_minutes = sum(minutes_since_midnight) / len(minutes_since_midnight)
        hours = int(average_minutes // 60)
        minutes = int(average_minutes % 60)
        average_arrival_time = f"{hours:02d}:{minutes:02d}"

    most_late_employee = None
    late_aggregate = (
        records.filter(status=AttendanceRecord.Status.LATE)
        .values('employee_id', 'employee__first_name', 'employee__last_name', 'employee__employee_code')
        .annotate(late_count=Count('id'), total_minutes=Sum('minutes_late'))
        .order_by('-late_count', '-total_minutes')
        .first()
    )
    if late_aggregate:
        most_late_employee = {
            'employee_id': str(late_aggregate['employee_id']),
            'name': f"{late_aggregate['employee__first_name']} {late_aggregate['employee__last_name']}",
            'employee_code': late_aggregate['employee__employee_code'],
            'late_count': late_aggregate['late_count'],
            'total_minutes_late': late_aggregate['total_minutes'] or 0,
        }

    return {
        'today': today.isoformat(),
        'attendance_method': _get_rule_or_default().attendance_method,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'attendance_rate': attendance_rate,
        'average_arrival_time': average_arrival_time,
        'most_late_employee': most_late_employee,
        'attendance_trend': _build_trend(),
        'recent_activity': _recent_activity(),
        'is_scanning': attendance_service.status().get('is_scanning', False),
        'scanner_status': attendance_service.status(),
    }


def _create_attendance_record(*, employee, recorded_by=None, check_in_time=None, date_value=None, notes=''):
    return attendance_service.create_attendance_record(
        employee=employee,
        recorded_by=recorded_by,
        check_in_time=check_in_time,
        date_value=date_value,
        notes=notes,
    )

class AttendanceAdminViewSet(viewsets.ViewSet):
    """
    Admin APIs for attendance management and fingerprint scanning.
    """
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get', 'put'])
    def rules(self, request):
        rule = _get_rule_or_default()
        
        if request.method == 'PUT':
            serializer = AttendanceRuleSerializer(rule, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
            
        serializer = AttendanceRuleSerializer(rule)
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'put'])
    def attendance_method(self, request):
        rule = _get_rule_or_default()

        if request.method == 'PUT':
            serializer = AttendanceRuleSerializer(rule, data={'attendance_method': request.data.get('attendance_method', rule.attendance_method)}, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({'attendance_method': serializer.data['attendance_method']})

        return Response({'attendance_method': rule.attendance_method})

    @action(detail=False, methods=['post'])
    def open_session(self, request):
        return self.start_scanning(request)

    @action(detail=False, methods=['post'])
    def close_session(self, request):
        return self.stop_scanning(request)

    @action(detail=False, methods=['get'])
    def current_session(self, request):
        return self.scanner_status(request)

    @action(detail=False, methods=['post'])
    def start_scanning(self, request):
        try:
            state = attendance_service.start()
            AttendanceLog.objects.create(
                admin=request.user,
                action='scanner_started',
                description=f"Attendance scanner service connected using {self._current_method_label()} mode."
            )
            return Response(state)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def stop_scanning(self, request):
        state = attendance_service.stop()
        AttendanceLog.objects.create(
            admin=request.user,
            action='scanner_stopped',
            description='Attendance scanner service disconnected.'
        )
        return Response(state)

    @action(detail=False, methods=['get'])
    def scanner_status(self, request):
        return Response(attendance_service.status())

    @action(detail=False, methods=['post'])
    def identify_fingerprint(self, request):
        serializer = AttendanceIdentifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rule = _get_rule_or_default()
        if rule.attendance_method != AttendanceMethod.FINGERPRINT:
            return Response({'detail': 'Fingerprint attendance is not the active method.'}, status=status.HTTP_400_BAD_REQUEST)

        if not fingerprint_service.is_connected():
            return Response({'detail': 'Fingerprint scanning is not active.'}, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data
        sample = payload.get('fingerprint_sample') or (payload.get('samples') or [None])[0]
        match = fingerprint_service.identify_sample(sample)
        if not match:
            return Response({'detail': 'Fingerprint not recognized.'}, status=status.HTTP_404_NOT_FOUND)

        employee = Employee.objects.filter(id=match['employee_id']).first()
        if not employee:
            return Response({'detail': 'Matched fingerprint template has no employee.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            record = _create_attendance_record(employee=employee, recorded_by=request.user, notes='Fingerprint scan recorded by admin PC.')
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        AttendanceLog.objects.create(
            employee=employee,
            admin=request.user,
            action='fingerprint_identified',
            description=f"Fingerprint matched template {match['template_id']} and created attendance record {record.id}."
        )
        return Response(AttendanceRecordSerializer(record).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def identify_face(self, request):
        rule = _get_rule_or_default()
        if rule.attendance_method != AttendanceMethod.FACE:
            return Response({'detail': 'Face recognition is not the active method.'}, status=status.HTTP_400_BAD_REQUEST)
        if not rule.face_recognition_enabled:
            return Response({'detail': 'Face recognition is disabled in attendance settings.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            snapshot = face_recognition_service.identify_faces(rule=rule)
        except RuntimeError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        created_records = []
        messages = []

        for face_result in snapshot.get('recognized_faces', []):
            employee = Employee.objects.filter(id=face_result['employee_id']).first()
            if not employee:
                messages.append(f"Employee {face_result['employee_id']} not found.")
                continue

            try:
                record = _create_attendance_record(
                    employee=employee,
                    recorded_by=request.user,
                    notes='Face recognition attendance recorded by admin PC.',
                )
            except ValueError as exc:
                messages.append(str(exc))
                continue

            AttendanceLog.objects.create(
                employee=employee,
                admin=request.user,
                action='face_identified',
                description=f"Face recognized employee {employee.employee_code} with confidence {face_result.get('confidence', 0.0):.4f}."
            )
            created_records.append(AttendanceRecordSerializer(record).data)

        payload = {
            **snapshot,
            'records': created_records,
            'messages': messages,
        }
        if created_records:
            return Response(payload, status=status.HTTP_201_CREATED)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def start_face_recognition(self, request):
        rule = _get_rule_or_default()
        if rule.attendance_method != AttendanceMethod.FACE:
            return Response({'detail': 'Face recognition is not the active method.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(attendance_service.start())
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def stop_face_recognition(self, request):
        return Response(attendance_service.stop())

    @action(detail=False, methods=['get'])
    def camera_status(self, request):
        return Response(face_recognition_service.get_camera_status())

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        return Response(_attendance_summary())

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        return Response(_attendance_summary())

    @action(detail=False, methods=['get'])
    def today_attendance(self, request):
        today = timezone.localdate()
        records = _attendance_queryset_base().filter(date=today).order_by('-check_in_time')
        serializer = AttendanceRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def history(self, request):
        queryset = _attendance_queryset_base()
        employee_id = request.query_params.get('employee_id')
        status_value = request.query_params.get('status')
        date_value = request.query_params.get('date')
        search = request.query_params.get('search')

        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if date_value:
            queryset = queryset.filter(date=date_value)
        if search:
            queryset = queryset.filter(
                Q(employee__first_name__icontains=search)
                | Q(employee__last_name__icontains=search)
                | Q(employee__employee_code__icontains=search)
            )

        queryset = queryset.order_by('-date', '-check_in_time')
        paginator = AttendancePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AttendanceRecordSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=False, methods=['get'])
    def records(self, request):
        return self.history(request)

    @action(detail=False, methods=['post'])
    def manual_attendance(self, request):
        serializer = AttendanceManualCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        employee = Employee.objects.filter(id=serializer.validated_data['employee_id']).first()
        if not employee:
            return Response({'detail': 'Employee not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            record = _create_attendance_record(
                employee=employee,
                recorded_by=request.user,
                check_in_time=serializer.validated_data.get('check_in_time'),
                date_value=serializer.validated_data.get('date'),
                notes=serializer.validated_data['notes'],
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        AttendanceLog.objects.create(
            employee=employee,
            admin=request.user,
            action='manual_attendance_created',
            description=f"Manual attendance created with reason: {serializer.validated_data['notes']}"
        )
        return Response(AttendanceRecordSerializer(record).data, status=status.HTTP_201_CREATED)

    def _current_method_label(self):
        rule = _get_rule_or_default()
        return 'face recognition' if rule.attendance_method == AttendanceMethod.FACE else 'fingerprint'

class AttendanceRecordViewSet(viewsets.ModelViewSet):
    """
    CRUD for Attendance Records (Admin usage).
    """
    queryset = _attendance_queryset_base()
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return AttendanceRecordUpdateSerializer
        return AttendanceRecordSerializer

    def get_queryset(self):
        return _attendance_queryset_base()

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_update(self, serializer):
        record = serializer.save()
        AttendanceLog.objects.create(
            action='attendance_modified',
            admin=self.request.user,
            employee=record.employee,
            description=f"Admin updated record {record.id} to status {record.status}."
        )

        # Notify the employee
        try:
            from apps.notifications.services import notification_service
            status_label = record.status.capitalize()
            notification_service.notify_user(
                user=record.employee.user,
                title='Attendance Status Updated',
                description=f'Admin updated your attendance status for {record.date.isoformat()} to {status_label}.',
                category='attendance',
                icon='attendance',
                reference_id=str(record.id)
            )
        except Exception as e:
            # Prevent failures from breaking response
            pass

    def perform_destroy(self, instance):
        AttendanceLog.objects.create(
            action='attendance_deleted',
            admin=self.request.user,
            employee=instance.employee,
            description=f"Admin deleted attendance record for {instance.date}."
        )
        instance.delete()


class AttendanceEmployeeViewSet(viewsets.ViewSet):
    """
    Employee APIs for attendance viewing only.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_employee(self):
        return getattr(self.request.user, 'employee_profile', None)

    @action(detail=False, methods=['post'])
    def scan(self, request):
        return Response({'detail': 'Employees do not scan fingerprints directly from the mobile app.'}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=False, methods=['get'])
    def today(self, request):
        employee = self._get_employee()
        if not employee:
            return Response({'detail': 'Not an employee.'}, status=status.HTTP_403_FORBIDDEN)
            
        today = timezone.localdate()
        record = AttendanceRecord.objects.filter(employee=employee, date=today).first()
        if not record:
            return Response({'detail': 'No attendance recorded today.'}, status=status.HTTP_404_NOT_FOUND)
            
        return Response(AttendanceRecordSerializer(record).data)

    @action(detail=False, methods=['get'])
    def history(self, request):
        employee = self._get_employee()
        if not employee:
            return Response({'detail': 'Not an employee.'}, status=status.HTTP_403_FORBIDDEN)
            
        records = AttendanceRecord.objects.filter(employee=employee).order_by('-date', '-check_in_time')
        serializer = AttendanceRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        employee = self._get_employee()
        if not employee:
            return Response({'detail': 'Not an employee.'}, status=status.HTTP_403_FORBIDDEN)
            
        records = AttendanceRecord.objects.filter(employee=employee)
        present = records.filter(status=AttendanceRecord.Status.PRESENT).count()
        late = records.filter(status=AttendanceRecord.Status.LATE).count()
        absent = records.filter(status=AttendanceRecord.Status.ABSENT).count()
        total = records.count()
        
        return Response({
            'present_days': present,
            'late_days': late,
            'absent_days': absent,
            'total_days': total,
            'attendance_percentage': round((present + late) / total * 100, 2) if total > 0 else 0,
        })
