import uuid

from django.conf import settings
from django.db import models

from apps.employees.models import Employee


class AttendanceMethod(models.TextChoices):
    """Supported attendance acquisition methods."""

    FINGERPRINT = 'fingerprint', 'Fingerprint'
    FACE = 'face', 'Face Recognition'


class AttendanceRule(models.Model):
    """
    Configuration for company attendance rules.
    Only one active rule should typically exist or be used.
    """
    attendance_method = models.CharField(
        max_length=32,
        choices=AttendanceMethod.choices,
        default=AttendanceMethod.FINGERPRINT,
        help_text='Selected attendance acquisition method.',
    )
    work_start_time = models.TimeField(help_text="Time work officially starts (e.g., 09:00:00)")
    grace_period_minutes = models.PositiveIntegerField(default=5, help_text="Minutes after start time before employee is considered late")
    maximum_late_minutes = models.PositiveIntegerField(default=60, help_text="Maximum allowed lateness before marked absent or penalized further")
    late_deduction_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Amount to deduct for lateness")
    attendance_enabled = models.BooleanField(default=True, help_text="Is the attendance system currently active")
    camera_enabled = models.BooleanField(default=True, help_text='Whether the camera subsystem is enabled.')
    camera_index = models.PositiveIntegerField(default=0, help_text='Local camera index used by the backend.')
    camera_resolution = models.CharField(max_length=32, default='1280x720', help_text='Camera resolution in WIDTHxHEIGHT format.')
    camera_fps = models.PositiveIntegerField(default=30, help_text='Target camera frame rate.')
    camera_auto_start = models.BooleanField(default=True, help_text='Automatically start the camera when attendance is enabled.')
    face_confidence_threshold = models.FloatField(default=0.65, help_text='Minimum confidence required to accept a face match.')
    face_recognition_enabled = models.BooleanField(default=True, help_text='Enable face recognition within the attendance service.')
    allow_multiple_face_detection = models.BooleanField(default=False, help_text='Recognize multiple visible faces in a single frame.')
    recognition_cooldown_seconds = models.PositiveIntegerField(default=5, help_text='Cooldown period before the same employee can be recognized again.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Rule: {self.work_start_time} start, {self.grace_period_minutes}m grace"

    def save(self, *args, **kwargs):
        if self.attendance_enabled:
            AttendanceRule.objects.exclude(pk=self.pk).update(attendance_enabled=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_active_rule(cls):
        return cls.objects.filter(attendance_enabled=True).order_by('-updated_at').first() or cls.objects.order_by('-updated_at').first()


class AttendanceSession(models.Model):
    """
    A specific period during which attendance can be recorded.
    """
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(max_length=255, unique=True, help_text="Cryptographically secure random token")
    generated_at = models.DateTimeField(auto_now_add=True)
    expiration_time = models.DateTimeField()
    session_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_attendance_sessions')
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-session_date', '-generated_at']

    def __str__(self):
        return f"Session {self.session_date} - {self.status}"


class AttendanceRecord(models.Model):
    """
    An employee's specific attendance entry for a day.
    """
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        LATE = 'late', 'Late'
        ABSENT = 'absent', 'Absent'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    check_in_time = models.DateTimeField()
    minutes_late = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=50, choices=Status.choices)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_attendance')
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['employee', 'date'], name='unique_attendance_record_per_employee_day'),
        ]
        ordering = ['-date', '-check_in_time']

    def __str__(self):
        return f"{self.employee} - {self.date} - {self.status}"


class AttendanceLog(models.Model):
    """
    Audit trail for attendance actions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=255, help_text="Action performed (e.g., 'fingerprint_enrolled', 'manual_attendance_created')")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_audit_logs', help_text="Admin who performed the action, if applicable")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_activity_logs', help_text="Employee affected by the action")
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} at {self.timestamp}"
