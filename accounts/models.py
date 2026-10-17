from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """3 ta rol: admin, doctor, patient."""
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrator'
        DOCTOR = 'doctor', 'Shifokor'
        PATIENT = 'patient', 'Bemor'

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.PATIENT, db_index=True)
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    middle_name = models.CharField(max_length=60, blank=True)
    language = models.CharField(max_length=5, default='uz')
    two_factor = models.BooleanField(default=False)

    @property
    def full_name(self):
        return ' '.join(x for x in (self.last_name, self.first_name, self.middle_name) if x) or self.username

    def save(self, *args, **kwargs):
        if self.role == self.Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)
