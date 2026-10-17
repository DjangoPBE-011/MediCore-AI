from django.conf import settings
from django.db import models
from django.db.models import Q

U = settings.AUTH_USER_MODEL


class Polyclinic(models.Model):
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    work_hours = models.CharField(max_length=60, default='08:00–18:00')
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name


class Specialization(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slot_minutes = models.PositiveSmallIntegerField(default=20)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name


class Doctor(models.Model):
    """Shifokor o'chirilmaydi, faqat faolsizlantiriladi (is_active=False)."""
    user = models.OneToOneField(U, on_delete=models.PROTECT, related_name='doctor')
    polyclinic = models.ForeignKey(Polyclinic, on_delete=models.PROTECT, related_name='doctors')
    specialization = models.ForeignKey(Specialization, on_delete=models.PROTECT, related_name='doctors')
    room = models.CharField(max_length=20, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    bio = models.TextField(blank=True)
    license_no = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.user.full_name


class Patient(models.Model):
    class Blood(models.TextChoices):
        O_POS = 'O+', 'O (I) +'; O_NEG = 'O-', 'O (I) −'
        A_POS = 'A+', 'A (II) +'; A_NEG = 'A-', 'A (II) −'
        B_POS = 'B+', 'B (III) +'; B_NEG = 'B-', 'B (III) −'
        AB_POS = 'AB+', 'AB (IV) +'; AB_NEG = 'AB-', 'AB (IV) −'

    user = models.OneToOneField(U, on_delete=models.PROTECT, related_name='patient')
    card_no = models.CharField(max_length=20, unique=True, blank=True)
    polyclinic = models.ForeignKey(Polyclinic, null=True, blank=True, on_delete=models.SET_NULL)
    family_doctor = models.ForeignKey(Doctor, null=True, blank=True, on_delete=models.SET_NULL, related_name='attached_patients')
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=[('m', 'Erkak'), ('f', 'Ayol')], blank=True)
    blood_group = models.CharField(max_length=4, choices=Blood.choices, blank=True)
    pinfl = models.CharField(max_length=14, unique=True, null=True, blank=True)
    address = models.CharField(max_length=200, blank=True)
    allergies = models.CharField(max_length=300, blank=True)
    chronic = models.CharField(max_length=300, blank=True)
    emergency_name = models.CharField(max_length=80, blank=True)
    emergency_phone = models.CharField(max_length=30, blank=True)

    def save(self, *a, **kw):
        super().save(*a, **kw)
        if not self.card_no:
            self.card_no = f'{(self.polyclinic_id or 0):02d}-{self.pk:05d}'
            super().save(update_fields=['card_no'])
    def __str__(self): return self.user.full_name


class FamilyMember(models.Model):
    owner = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='family')
    full_name = models.CharField(max_length=120)
    relation = models.CharField(max_length=30)
    birth_date = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=4, blank=True)


class Schedule(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='schedules')
    weekday = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(7)])  # 0=dushanba
    start = models.TimeField()
    end = models.TimeField()
    slot_minutes = models.PositiveSmallIntegerField(default=20)
    class Meta:
        unique_together = ('doctor', 'weekday')


class Appointment(models.Model):
    class S(models.TextChoices):
        PENDING = 'pending', 'Kutilmoqda'
        CONFIRMED = 'confirmed', 'Tasdiqlangan'
        IN_PROGRESS = 'in_progress', 'Qabul jarayonida'
        DONE = 'done', 'Yakunlangan'
        CANCELLED = 'cancelled', 'Bekor qilingan'
        NO_SHOW = 'no_show', 'Kelmagan'

    ACTIVE = ('pending', 'confirmed', 'in_progress')

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='appointments')
    family_member = models.ForeignKey(FamilyMember, null=True, blank=True, on_delete=models.SET_NULL)
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name='appointments')
    date = models.DateField(db_index=True)
    time = models.TimeField()
    status = models.CharField(max_length=12, choices=S.choices, default=S.PENDING, db_index=True)
    reason = models.CharField(max_length=200, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'time']
        constraints = [
            # ikki marta yozilishning oldini olish (baza darajasida)
            models.UniqueConstraint(fields=['doctor', 'date', 'time'],
                                    condition=Q(status__in=['pending', 'confirmed', 'in_progress']),
                                    name='uniq_active_slot_per_doctor'),
        ]


class QueueTicket(models.Model):
    class S(models.TextChoices):
        WAITING = 'waiting', 'Navbatda'
        CALLED = 'called', 'Qabulda'
        DONE = 'done', 'Tugagan'
        CANCELLED = 'cancelled', 'Bekor'

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='tickets')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='tickets')
    date = models.DateField(db_index=True)
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=S.choices, default=S.WAITING)
    notify_before = models.PositiveSmallIntegerField(default=2)
    notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['date', 'number']
        unique_together = ('doctor', 'date', 'number')


class ICD10(models.Model):
    """Tashxislar katalogi. Tizim o'zi tashxis qo'ymaydi."""
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=250)
    section = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    class Meta: ordering = ['code']
    def __str__(self): return f'{self.code} {self.name}'


class MedicalRecord(models.Model):
    """Ko'rik natijasi (shifokor yozadi, bemor faqat o'qiydi)."""
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='records')
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name='records')
    appointment = models.ForeignKey(Appointment, null=True, blank=True, on_delete=models.SET_NULL)
    complaint = models.TextField(blank=True)
    objective = models.TextField(blank=True)
    diagnosis = models.ForeignKey(ICD10, null=True, blank=True, on_delete=models.PROTECT)
    recommendations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']


class Prescription(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='prescriptions')
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT)
    number = models.CharField(max_length=30, unique=True, blank=True)
    valid_until = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']

    def save(self, *a, **kw):
        super().save(*a, **kw)
        if not self.number:
            self.number = f'RX-{self.created_at:%Y}-{self.pk:04d}'
            super().save(update_fields=['number'])


class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='items')
    medicine = models.CharField(max_length=120)
    dose = models.CharField(max_length=80, blank=True)
    times_per_day = models.PositiveSmallIntegerField(default=1)
    days = models.PositiveSmallIntegerField(default=7)


class LabResult(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_results')
    test = models.CharField(max_length=100)       # Umumiy qon tahlili
    indicator = models.CharField(max_length=80)   # Gemoglobin
    value = models.DecimalField(max_digits=9, decimal_places=2)
    unit = models.CharField(max_length=20, blank=True)
    ref_low = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    ref_high = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    taken_at = models.DateField()
    class Meta: ordering = ['-taken_at']

    @property
    def flag(self):
        if self.ref_low is not None and self.value < self.ref_low: return 'low'
        if self.ref_high is not None and self.value > self.ref_high: return 'high'
        return 'normal'


class LabOrder(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_orders')
    test = models.CharField(max_length=100)
    lab = models.CharField(max_length=100, blank=True)
    price = models.PositiveIntegerField(default=0)
    scheduled_for = models.DateTimeField()
    status = models.CharField(max_length=12, default='new')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']


class HealthMetric(models.Model):
    class K(models.TextChoices):
        BP = 'bp', 'Qon bosimi'; SUGAR = 'sugar', 'Qand'; WEIGHT = 'weight', 'Vazn'; PULSE = 'pulse', 'Puls'
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='metrics')
    kind = models.CharField(max_length=8, choices=K.choices)
    value = models.DecimalField(max_digits=7, decimal_places=2)
    value2 = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)  # diastolik bosim
    measured_at = models.DateTimeField()
    class Meta: ordering = ['-measured_at']

    @property
    def status(self):
        v, v2 = float(self.value), float(self.value2 or 0)
        if self.kind == 'bp':
            return 'high' if v >= 135 or v2 >= 85 else ('low' if v < 90 else 'normal')
        if self.kind == 'sugar':
            return 'high' if v > 7.0 else ('low' if v < 3.9 else 'normal')
        if self.kind == 'pulse':
            return 'high' if v > 100 else ('low' if v < 50 else 'normal')
        return 'normal'


class MedicationReminder(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='reminders')
    name = models.CharField(max_length=120)
    dose = models.CharField(max_length=80, blank=True)
    time = models.TimeField()
    active = models.BooleanField(default=True)


class ReminderLog(models.Model):
    reminder = models.ForeignKey(MedicationReminder, on_delete=models.CASCADE, related_name='logs')
    date = models.DateField()
    taken = models.BooleanField(default=False)
    class Meta: unique_together = ('reminder', 'date')


class Vaccination(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='vaccinations')
    family_member = models.ForeignKey(FamilyMember, null=True, blank=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    due_date = models.DateField()
    done_date = models.DateField(null=True, blank=True)
    class Meta: ordering = ['due_date']


class Review(models.Model):
    """Sharh faqat qabuldan keyin (yakunlangan qabul bor bo'lsa) shifokorga yoziladi."""
    author = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, null=True, blank=True, on_delete=models.CASCADE, related_name='reviews')
    place = models.ForeignKey('catalog.Place', null=True, blank=True, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']
