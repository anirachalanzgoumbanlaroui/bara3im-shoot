from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model for Bara3im Shoot.
    Extends Django's AbstractUser with additional fields for future milestones.
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        PHOTOGRAPHER = 'photographer', 'Photographer'
        SELLER = 'seller', 'Seller'
        CLOWN = 'clown', 'Clown'

    phone_number = models.CharField(max_length=20, blank=True, default='')
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ADMIN,
    )

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'
