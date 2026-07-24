import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class Location(models.Model):
    """
    Permanent work location for Bara3im Shoot (e.g. Ardis, Sablette).
    Seeded via data migration — new locations are not created via API.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=10, blank=True, default='📍')
    color_hex = models.CharField(
        max_length=7, blank=True, default='#1565C0',
        help_text="Primary accent color for this location (hex)."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.icon} {self.name}"


class WorkDay(models.Model):
    """
    One working day at ONE location.
    Uniqueness is (location, date) — Ardis and Sablette each have their own
    independent WorkDay for the same calendar date.
    """

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='work_days'
    )
    date = models.DateField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN
    )
    photographer_unit_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Price per photo for photographers."
    )
    clown_unit_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Price per photo for clowns."
    )
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_workdays'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('location', 'date')]
        ordering = ['-date']

    def __str__(self):
        return f"{self.location.name} — {self.date}"

    def clean(self):
        if self.status == self.Status.CLOSED and not self.closed_at:
            from django.utils import timezone
            self.closed_at = timezone.now()


class DailyTeam(models.Model):
    """
    A team of 1 Photographer + 1 Clown for a specific WorkDay.
    Each photographer/clown can only appear once per WorkDay.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_day = models.ForeignKey(
        WorkDay, on_delete=models.CASCADE, related_name='teams'
    )
    photographer = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='teams_as_photographer',
        limit_choices_to={'role': 'photographer'}
    )
    clown = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='teams_as_clown',
        limit_choices_to={'role': 'clown'}
    )
    team_name = models.CharField(max_length=150, blank=True, null=True)
    team_photo_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-work_day__date', 'team_name']
        unique_together = [
            ('work_day', 'photographer'),
            ('work_day', 'clown'),
        ]

    def __str__(self):
        name = self.team_name or f"{self.photographer.first_name} & {self.clown.first_name}"
        return f"{name} @ {self.work_day}"

    def clean(self):
        if self.photographer.role != 'photographer':
            raise ValidationError("Photographer must have the role 'photographer'.")
        if self.clown.role != 'clown':
            raise ValidationError("Clown must have the role 'clown'.")

        conflict_photo = DailyTeam.objects.filter(
            work_day=self.work_day,
            photographer=self.photographer
        ).exclude(pk=self.pk)
        if conflict_photo.exists():
            raise ValidationError(
                f"{self.photographer.first_name} is already in a team today."
            )
        conflict_clown = DailyTeam.objects.filter(
            work_day=self.work_day,
            clown=self.clown
        ).exclude(pk=self.pk)
        if conflict_clown.exists():
            raise ValidationError(
                f"{self.clown.first_name} is already in a team today."
            )


class DailyEmployeePerformance(models.Model):
    """
    Tracks an employee's photo output for a WorkDay.
    Earnings are calculated dynamically, NOT stored.
    """

    class AdjustmentType(models.TextChoices):
        AUTOMATIC = 'automatic', 'Automatic'
        MANUAL = 'manual', 'Manual'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        'employees.Employee', on_delete=models.CASCADE, related_name='performances'
    )
    work_day = models.ForeignKey(
        WorkDay, on_delete=models.CASCADE, related_name='performances'
    )
    team = models.ForeignKey(
        DailyTeam, on_delete=models.CASCADE, related_name='performances'
    )
    photo_count = models.PositiveIntegerField(default=0)
    adjustment_type = models.CharField(
        max_length=20,
        choices=AdjustmentType.choices,
        default=AdjustmentType.AUTOMATIC
    )
    adjustment_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-work_day__date', 'employee__first_name']
        unique_together = [('work_day', 'employee')]

    def __str__(self):
        return f"{self.employee.first_name} on {self.work_day.date}: {self.photo_count} photos"


class DailyOperationLog(models.Model):
    """
    Audit log for important actions in the Daily Operations module.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_day = models.ForeignKey(
        WorkDay, on_delete=models.CASCADE, related_name='audit_logs'
    )
    action = models.CharField(max_length=150)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} — {self.work_day} by {self.user}"


class SellerDailyOperation(models.Model):
    """
    Seller's daily earnings for a specific WorkDay.
    Each seller has ONE record per WorkDay.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='seller_daily_operations',
        limit_choices_to={'role': 'seller'}
    )
    work_day = models.ForeignKey(
        WorkDay, on_delete=models.CASCADE, related_name='seller_operations'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-work_day__date', 'seller__first_name']
        unique_together = [('work_day', 'seller')]

    def __str__(self):
        return f"{self.seller.first_name} @ {self.work_day}: {self.amount} DA"

    def clean(self):
        if self.seller.role != 'seller':
            raise ValidationError("Employee must have the role 'seller'.")
