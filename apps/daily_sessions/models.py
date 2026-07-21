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
    Represents one working day session for Bara3im Shoot.
    No status locking — admin can always manage teams and earnings freely.
    Unit prices apply globally across all locations for that day.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True)
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

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Work Day {self.date}"


class DailyLocation(models.Model):
    """
    A specific location's operational slot for a given work day.
    One record per (work_day × location). Acts as the pivot that owns
    all teams and seller operations for that day/location combination.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_day = models.ForeignKey(
        WorkDay, on_delete=models.CASCADE, related_name='daily_locations'
    )
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='daily_locations'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['location__name']
        unique_together = [('work_day', 'location')]

    def __str__(self):
        return f"{self.location.name} — {self.work_day.date}"


class DailyTeam(models.Model):
    """
    Represents a team (1 Photographer + 1 Clown) for a specific DailyLocation.
    Cross-location uniqueness is enforced: one photographer and one clown
    can only appear at ONE location per work day.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    daily_location = models.ForeignKey(
        DailyLocation, on_delete=models.CASCADE, related_name='teams'
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
        ordering = ['-daily_location__work_day__date', 'team_name']
        unique_together = [
            ('daily_location', 'photographer'),
            ('daily_location', 'clown'),
        ]

    def __str__(self):
        name = self.team_name or f"{self.photographer.first_name} & {self.clown.first_name}"
        return f"{name} @ {self.daily_location}"

    def clean(self):
        if self.photographer.role != 'photographer':
            raise ValidationError("Photographer must have the role 'photographer'.")
        if self.clown.role != 'clown':
            raise ValidationError("Clown must have the role 'clown'.")

        # Only prevent duplicate assignment within the same daily location
        conflict_photo = DailyTeam.objects.filter(
            daily_location=self.daily_location,
            photographer=self.photographer
        ).exclude(pk=self.pk)
        if conflict_photo.exists():
            raise ValidationError(
                f"{self.photographer.first_name} is already in a team at this location."
            )
        conflict_clown = DailyTeam.objects.filter(
            daily_location=self.daily_location,
            clown=self.clown
        ).exclude(pk=self.pk)
        if conflict_clown.exists():
            raise ValidationError(
                f"{self.clown.first_name} is already in a team at this location."
            )


class DailyEmployeePerformance(models.Model):
    """
    Represents operational data for an employee's performance in a team.
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
    daily_location = models.ForeignKey(
        DailyLocation, on_delete=models.CASCADE, related_name='performances', null=True, blank=True
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
        return f"{self.action} - {self.work_day.date} by {self.user}"


class SellerDailyOperation(models.Model):
    """
    Represents daily operations and earnings for a Seller at a specific DailyLocation.
    Each seller has ONLY ONE earning per DailyLocation (and per work day across all locations).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='seller_daily_operations',
        limit_choices_to={'role': 'seller'}
    )
    daily_location = models.ForeignKey(
        DailyLocation,
        on_delete=models.CASCADE,
        related_name='seller_operations'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-daily_location__work_day__date', 'seller__first_name']
        unique_together = [('daily_location', 'seller')]

    def __str__(self):
        return f"{self.seller.first_name} @ {self.daily_location}: {self.amount} DA"

    def clean(self):
        if self.seller.role != 'seller':
            raise ValidationError("Employee must have the role 'seller'.")
        # Cross-location uniqueness: a seller can only appear at ONE location per work day
        work_day = self.daily_location.work_day
        conflict = SellerDailyOperation.objects.filter(
            daily_location__work_day=work_day,
            seller=self.seller
        ).exclude(pk=self.pk)
        if conflict.exists():
            raise ValidationError(
                f"{self.seller.first_name} is already assigned to another location today."
            )
