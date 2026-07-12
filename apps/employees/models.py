import uuid
from django.db import models
from django.conf import settings

class Employee(models.Model):
    """
    Employee model for Bara3im Shoot.
    It contains specific business data for employees (Photographers and Sellers).
    This model separates the business data from the User model (which handles authentication).
    """

    class Role(models.TextChoices):
        PHOTOGRAPHER = 'photographer', 'Photographer',
        SELLER = 'seller', 'Seller',
        CLOWN = 'clown', 'Clown'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee_profile'
    )
    employee_code = models.CharField(max_length=50, unique=True, blank=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20)
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    hiring_date = models.DateField()
    role = models.CharField(max_length=50, choices=Role.choices)
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.ACTIVE
    )
    avatar = models.ImageField(upload_to='employees/avatars/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    fingerprint_registered = models.BooleanField(default=False)
    fingerprint_template_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    fingerprint_registered_at = models.DateTimeField(blank=True, null=True)
    face_registered = models.BooleanField(default=False)
    face_embedding = models.JSONField(blank=True, null=True)
    face_registered_at = models.DateTimeField(blank=True, null=True)
    face_last_updated = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_code})"

    def save(self, *args, **kwargs):
        # Automatically generate employee code if not provided
        if not self.employee_code:
            last_employee = Employee.objects.all().order_by('created_at').last()
            if not last_employee or not last_employee.employee_code.startswith('EMP-'):
                self.employee_code = 'EMP-0001'
            else:
                try:
                    last_num = int(last_employee.employee_code.split('-')[1])
                    self.employee_code = f'EMP-{last_num + 1:04d}'
                except (IndexError, ValueError):
                    self.employee_code = f'EMP-{uuid.uuid4().hex[:6].upper()}'
        super().save(*args, **kwargs)


class Bonus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='bonuses')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Bonus: {self.amount} DA for {self.employee} on {self.date}"


class Advance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='advances')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Advance: {self.amount} DA for {self.employee} on {self.date}"


class Deduction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='deductions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Deduction: {self.amount} DA for {self.employee} on {self.date}"

