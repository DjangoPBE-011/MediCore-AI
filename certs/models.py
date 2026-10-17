import secrets
from django.db import models
from django.utils import timezone


def _token():
    return secrets.token_urlsafe(24)


class Certificate(models.Model):
    class S(models.TextChoices):
        DRAFT = 'draft', 'Qoralama'
        PENDING = 'pending', 'Tasdiqlash kutilmoqda'
        APPROVED = 'approved', 'Tasdiqlangan'
        REJECTED = 'rejected', 'Rad etilgan'
        CANCELLED = 'cancelled', 'Bekor qilingan'
        EXPIRED = 'expired', 'Muddati tugagan'

    class Type(models.TextChoices):
        POOL = 'pool', 'Bassein'
        SPORT = 'sport', 'Sport'
        SCHOOL = 'school', 'Maktab (086/u)'
        WORK = 'work', 'Ish joyi'
        SICK = 'sick', 'Kasallik varaqasi'
        OTHER = 'other', 'Boshqa'

    number = models.CharField(max_length=30, unique=True, blank=True)
    patient = models.ForeignKey('clinic.Patient', on_delete=models.PROTECT, related_name='certificates')
    doctor = models.ForeignKey('clinic.Doctor', on_delete=models.PROTECT, related_name='certificates')
    kind = models.CharField(max_length=10, choices=Type.choices, default=Type.OTHER)
    conclusion = models.TextField(blank=True)
    diagnosis = models.ForeignKey('clinic.ICD10', null=True, blank=True, on_delete=models.PROTECT)
    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=S.choices, default=S.DRAFT, db_index=True)
    reject_reason = models.CharField(max_length=250, blank=True)
    cancel_reason = models.CharField(max_length=250, blank=True)
    # ERI (E-IMZO): oddiy "tasdiqlash" tugmasi ERI emas, imzo ma'lumotlari alohida saqlanadi
    signature_serial = models.CharField(max_length=80, blank=True)
    signature_data = models.TextField(blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    qr_token = models.CharField(max_length=64, unique=True, default=_token)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *a, **kw):
        super().save(*a, **kw)
        if not self.number:
            self.number = f'OP{self.doctor.polyclinic_id:02d}-{timezone.now():%Y}-{self.pk:05d}'
            super().save(update_fields=['number'])

    @property
    def effective_status(self):
        if self.status == self.S.APPROVED and self.valid_until and self.valid_until < timezone.localdate():
            return self.S.EXPIRED
        return self.status

    @property
    def editable(self):
        return self.status in (self.S.DRAFT, self.S.REJECTED)


class ShareLink(models.Model):
    """Bemor ma'lumotnomani tanlab, vaqt cheklovi bilan ulashadi."""
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name='shares')
    token = models.CharField(max_length=64, unique=True, default=_token)
    show_conclusion = models.BooleanField(default=True)
    show_diagnosis = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_valid(self):
        return self.expires_at > timezone.now()
