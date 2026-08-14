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
        DRAFT = 'draft', 'Draft'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        LOCKED = 'locked', 'Locked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='work_days'
    )
    date = models.DateField()
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.DRAFT
    )
    photographer_unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=45,
        help_text="Price per photo for photographers (Normal price)."
    )
    clown_unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=50,
        help_text="Price per photo for clowns (Normal price)."
    )
    dynamic_pricing_enabled = models.BooleanField(
        default=False,
        help_text="Whether dynamic photo unit pricing is active for this WorkDay."
    )
    low_photo_threshold = models.PositiveIntegerField(
        default=40,
        help_text="Photo threshold for low volume pricing."
    )
    high_photo_threshold = models.PositiveIntegerField(
        default=80,
        help_text="Photo threshold for high volume pricing."
    )
    low_photographer_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=40,
        help_text="Photographer unit price when total photos < low_photo_threshold."
    )
    low_clown_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=45,
        help_text="Clown unit price when total photos < low_photo_threshold."
    )
    high_photographer_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=50,
        help_text="Photographer unit price when total photos > high_photo_threshold."
    )
    high_clown_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=55,
        help_text="Clown unit price when total photos > high_photo_threshold."
    )
    low_tier_active = models.BooleanField(
        default=True,
        help_text="Whether low volume pricing tier is active."
    )
    normal_tier_active = models.BooleanField(
        default=True,
        help_text="Whether normal volume pricing tier is active."
    )
    high_tier_active = models.BooleanField(
        default=True,
        help_text="Whether high volume pricing tier is active."
    )
    is_manually_overridden = models.BooleanField(
        default=False,
        help_text="Whether pricing has been manually overridden by admin."
    )
    override_photographer_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Manually overridden photographer unit price."
    )
    override_clown_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Manually overridden clown unit price."
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
        constraints = [
            models.UniqueConstraint(
                fields=["location", "date"],
                name="unique_workday_location_date",
            )
        ]
        ordering = ['-date']

    def __str__(self):
        return f"{self.location.name} — {self.date}"

    def clean(self):
        if self.status in (self.Status.COMPLETED, self.Status.LOCKED) and not self.closed_at:
            from django.utils import timezone
            self.closed_at = timezone.now()

        if self.low_photo_threshold >= self.high_photo_threshold:
            raise ValidationError("low_photo_threshold must be strictly less than high_photo_threshold.")

        for price_field in [
            self.photographer_unit_price, self.clown_unit_price,
            self.low_photographer_price, self.low_clown_price,
            self.high_photographer_price, self.high_clown_price,
        ]:
            if price_field < 0:
                raise ValidationError("Price values cannot be negative.")

        if self.override_photographer_price is not None and self.override_photographer_price < 0:
            raise ValidationError("Override price cannot be negative.")
        if self.override_clown_price is not None and self.override_clown_price < 0:
            raise ValidationError("Override price cannot be negative.")

    def get_resolved_unit_prices(self, photo_count=None):
        """
        Calculates applicable unit prices based on dynamic pricing state, thresholds, photo count, and tier activation.
        Exact boundary rules:
        - 0–39 photos (< low_photo_threshold 40): Low pricing (if active)
        - 40–80 photos (low_photo_threshold 40 <= photos <= high_photo_threshold 80): Normal pricing (if active)
        - 81+ photos (> high_photo_threshold 80): High pricing (if active)
        """
        if self.is_manually_overridden and self.override_photographer_price is not None and self.override_clown_price is not None:
            return {
                'photographer_unit_price': self.override_photographer_price,
                'clown_unit_price': self.override_clown_price,
                'tier': 'override',
                'is_overridden': True,
            }

        if not self.dynamic_pricing_enabled:
            return {
                'photographer_unit_price': self.photographer_unit_price,
                'clown_unit_price': self.clown_unit_price,
                'tier': 'normal',
                'is_overridden': False,
            }

        if photo_count is None:
            photo_count = sum(t.team_photo_count for t in self.teams.all())

        target_tier = 'normal'
        if photo_count < self.low_photo_threshold:
            target_tier = 'low'
        elif photo_count > self.high_photo_threshold:
            target_tier = 'high'

        # Check activation status with fallback
        selected_tier = 'normal'
        if target_tier == 'low':
            if self.low_tier_active:
                selected_tier = 'low'
            elif self.normal_tier_active:
                selected_tier = 'normal'
            elif self.high_tier_active:
                selected_tier = 'high'
        elif target_tier == 'high':
            if self.high_tier_active:
                selected_tier = 'high'
            elif self.normal_tier_active:
                selected_tier = 'normal'
            elif self.low_tier_active:
                selected_tier = 'low'
        else: # normal
            if self.normal_tier_active:
                selected_tier = 'normal'
            elif self.low_tier_active:
                selected_tier = 'low'
            elif self.high_tier_active:
                selected_tier = 'high'

        if selected_tier == 'low':
            return {
                'photographer_unit_price': self.low_photographer_price,
                'clown_unit_price': self.low_clown_price,
                'tier': 'low',
                'is_overridden': False,
            }
        elif selected_tier == 'high':
            return {
                'photographer_unit_price': self.high_photographer_price,
                'clown_unit_price': self.high_clown_price,
                'tier': 'high',
                'is_overridden': False,
            }
        else:
            return {
                'photographer_unit_price': self.photographer_unit_price,
                'clown_unit_price': self.clown_unit_price,
                'tier': 'normal',
                'is_overridden': False,
            }


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
        on_delete=models.PROTECT,
        related_name='teams_as_photographer',
        limit_choices_to={'role': 'photographer'}
    )
    clown = models.ForeignKey(
        'employees.Employee',
        on_delete=models.PROTECT,
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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            from apps.daily_sessions.models import DailyEmployeePerformance
            for emp in [self.photographer, self.clown]:
                if emp:
                    perf, created = DailyEmployeePerformance.objects.get_or_create(
                        work_day=self.work_day,
                        employee=emp,
                        defaults={
                            'team': self,
                            'photo_count': self.team_photo_count,
                            'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
                        }
                    )
                    if not created and perf.adjustment_type == DailyEmployeePerformance.AdjustmentType.AUTOMATIC:
                        if perf.photo_count != self.team_photo_count or perf.team_id != self.id:
                            perf.photo_count = self.team_photo_count
                            perf.team = self
                            perf.save(update_fields=['photo_count', 'team', 'updated_at'])
        except Exception:
            pass

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
        'employees.Employee', on_delete=models.PROTECT, related_name='performances'
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
        on_delete=models.PROTECT,
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
