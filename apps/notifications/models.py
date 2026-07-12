import uuid
from django.db import models
from django.conf import settings

class NotificationCategory(models.TextChoices):
    ATTENDANCE = 'attendance', 'Attendance'
    WORK_RESULTS = 'work_results', 'Work Results'
    PAYROLL = 'payroll', 'Payroll'
    SYSTEM = 'system', 'System'

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    description = models.TextField()
    icon = models.CharField(max_length=100, blank=True, null=True, help_text="Icon identifier for the frontend")
    category = models.CharField(max_length=50, choices=NotificationCategory.choices, default=NotificationCategory.SYSTEM)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Allows attaching a related entity (e.g., WorkDay id, AttendanceRecord id) for deep linking
    reference_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.category}] {self.title} to {self.user}"
