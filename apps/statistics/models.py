import uuid
from django.db import models


class Achievement(models.Model):
    """
    Badge / Achievement model for Bara3im Shoot employees.
    Supports standard badges as well as the special legendary 'NADJIB' badge.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=20, default='🏆')
    is_legendary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.icon} {self.name}"


class EmployeeAchievement(models.Model):
    """
    Employee achievement tracking model.
    Records when an employee earns a specific achievement/badge.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='employee_achievements'
    )
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name='earned_by'
    )
    earned_at = models.DateTimeField(auto_now_add=True)
    period = models.CharField(max_length=50, blank=True, default='all_time')
    location = models.ForeignKey(
        'daily_sessions.Location',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.employee} — {self.achievement.name} ({self.period})"
