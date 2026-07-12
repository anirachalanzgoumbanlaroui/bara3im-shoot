"""High-level attendance service that selects the active provider.

The views call this service instead of talking to providers directly. That keeps
method selection, camera lifecycle, and recognition status in one place.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone

from apps.attendance.models import AttendanceMethod, AttendanceRecord, AttendanceRule, AttendanceLog
from apps.employees.models import Employee

from .face.service import face_recognition_service
from .fingerprint.service import fingerprint_service


class AttendanceService:
    """Coordinates attendance-method selection and provider lifecycle."""

    def get_active_rule(self):
        return AttendanceRule.get_active_rule()

    def get_current_method(self):
        rule = self.get_active_rule()
        return rule.attendance_method if rule else AttendanceMethod.FINGERPRINT

    def start(self):
        rule = self.get_active_rule()
        if rule is None:
            raise RuntimeError('No attendance rule is configured.')

        if rule.attendance_method == AttendanceMethod.FACE:
            state = face_recognition_service.start_camera(rule)
            if not rule.camera_enabled:
                state['camera_warning'] = 'Camera is disabled in settings.'
            return state

        state = fingerprint_service.connect()
        return {**state, 'provider': 'fingerprint', 'templates': len(fingerprint_service.list_templates())}

    def stop(self):
        rule = self.get_active_rule()
        if rule and rule.attendance_method == AttendanceMethod.FACE:
            return face_recognition_service.stop_camera()
        return fingerprint_service.disconnect()

    def status(self):
        rule = self.get_active_rule()
        if rule and rule.attendance_method == AttendanceMethod.FACE:
            camera_state = face_recognition_service.get_camera_status()
            return {
                'connected': camera_state['connected'],
                'provider': 'insightface',
                'attendance_method': rule.attendance_method,
                'is_scanning': camera_state['connected'],
                'camera_status': camera_state,
                'templates': camera_state.get('faces_loaded', 0),
            }

        return {
            'connected': fingerprint_service.is_connected(),
            'provider': 'fingerprint',
            'attendance_method': rule.attendance_method if rule else AttendanceMethod.FINGERPRINT,
            'is_scanning': fingerprint_service.is_connected(),
            'templates': len(fingerprint_service.list_templates()) if fingerprint_service.is_connected() else 0,
        }

    def create_attendance_record(self, *, employee, recorded_by=None, check_in_time=None, date_value=None, notes=''):
        now = check_in_time or timezone.now()
        record_date = date_value or timezone.localdate(now)
        rule = self.get_active_rule()

        if not rule.attendance_enabled:
            raise ValueError('Attendance is currently disabled.')
        if employee.status != Employee.Status.ACTIVE:
            raise ValueError('Inactive employees cannot check in.')
        if AttendanceRecord.objects.filter(employee=employee, date=record_date).exists():
            raise ValueError('Attendance already recorded for this employee today.')

        status_value, minutes_late = self._calculate_status(now, rule)
        if status_value == AttendanceRecord.Status.ABSENT and minutes_late < 0:
            minutes_late = 0

        record = AttendanceRecord.objects.create(
            employee=employee,
            date=record_date,
            check_in_time=now,
            status=status_value,
            minutes_late=minutes_late,
            recorded_by=recorded_by,
            notes=notes,
        )

        AttendanceLog.objects.create(
            employee=employee,
            admin=recorded_by if getattr(recorded_by, 'is_staff', False) else None,
            action='attendance_created',
            description=f'Attendance recorded as {status_value} for {record_date.isoformat()}.',
        )

        # Notify the employee
        try:
            from apps.notifications.services import notification_service
            status_label = status_value.capitalize()
            check_in_str = timezone.localtime(now).strftime('%H:%M')
            if status_value == AttendanceRecord.Status.LATE:
                desc = f'Your attendance was recorded as Late for {record_date.isoformat()} (arrived at {check_in_str}, {minutes_late} minutes late).'
            elif status_value == AttendanceRecord.Status.PRESENT:
                desc = f'Your attendance was recorded as Present for {record_date.isoformat()} (arrived at {check_in_str}).'
            else:
                desc = f'Your attendance was recorded as Absent for {record_date.isoformat()}.'

            notification_service.notify_user(
                user=employee.user,
                title='Attendance Recorded',
                description=desc,
                category='attendance',
                icon='attendance',
                reference_id=str(record.id)
            )
        except Exception as e:
            # Prevent failures from blocking the return
            pass

        return record

    def _calculate_status(self, now, rule):
        start_datetime = self._make_aware_for_today(now.date(), rule.work_start_time)
        grace_end = start_datetime + timedelta(minutes=rule.grace_period_minutes)
        maximum_late_end = start_datetime + timedelta(minutes=rule.maximum_late_minutes)

        if now <= grace_end:
            return AttendanceRecord.Status.PRESENT, 0

        minutes_late = int((now - start_datetime).total_seconds() / 60)
        if now <= maximum_late_end:
            return AttendanceRecord.Status.LATE, minutes_late

        return AttendanceRecord.Status.ABSENT, minutes_late

    def _make_aware_for_today(self, today, value):
        if timezone.is_aware(value):
            return value
        current_tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime.combine(today, value), current_tz)


attendance_service = AttendanceService()
