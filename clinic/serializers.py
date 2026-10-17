from django.utils import timezone
from rest_framework import serializers
from . import models as m
from .services import queue_info


class PolyclinicSerializer(serializers.ModelSerializer):
    class Meta: model = m.Polyclinic; fields = '__all__'


class SpecializationSerializer(serializers.ModelSerializer):
    class Meta: model = m.Specialization; fields = '__all__'


class DoctorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    specialization_name = serializers.CharField(source='specialization.name', read_only=True)
    polyclinic_name = serializers.CharField(source='polyclinic.name', read_only=True)
    rating = serializers.SerializerMethodField()
    queue_length = serializers.SerializerMethodField()

    class Meta:
        model = m.Doctor
        fields = ['id', 'user', 'full_name', 'polyclinic', 'polyclinic_name', 'specialization', 'specialization_name',
                  'room', 'experience_years', 'bio', 'license_no', 'is_active', 'rating', 'queue_length']

    def get_rating(self, o):
        from django.db.models import Avg
        r = o.reviews.aggregate(a=Avg('rating'))['a']
        return round(r, 1) if r else None

    def get_queue_length(self, o):
        return m.QueueTicket.objects.filter(doctor=o, date=timezone.localdate(), status='waiting').count()


class DoctorCreateSerializer(serializers.Serializer):
    """Admin shifokor yaratadi: foydalanuvchi + shifokor profili birga."""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    middle_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    polyclinic = serializers.PrimaryKeyRelatedField(queryset=m.Polyclinic.objects.all())
    specialization = serializers.PrimaryKeyRelatedField(queryset=m.Specialization.objects.all())
    room = serializers.CharField(required=False, allow_blank=True)
    experience_years = serializers.IntegerField(required=False, default=0)

    def create(self, d):
        from django.contrib.auth import get_user_model
        U = get_user_model()
        if U.objects.filter(username=d['username']).exists():
            raise serializers.ValidationError({'username': 'Band'})
        u = U.objects.create_user(username=d['username'], password=d['password'], first_name=d['first_name'],
                                  last_name=d['last_name'], middle_name=d.get('middle_name', ''),
                                  phone=d.get('phone', ''), role='doctor')
        return m.Doctor.objects.create(user=u, polyclinic=d['polyclinic'], specialization=d['specialization'],
                                       room=d.get('room', ''), experience_years=d.get('experience_years', 0))


class PatientSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    age = serializers.SerializerMethodField()
    class Meta:
        model = m.Patient
        fields = ['id', 'user', 'full_name', 'phone', 'card_no', 'polyclinic', 'family_doctor', 'birth_date', 'age',
                  'gender', 'blood_group', 'pinfl', 'address', 'allergies', 'chronic',
                  'emergency_name', 'emergency_phone']
        read_only_fields = ['card_no', 'user']
    def get_age(self, o):
        if not o.birth_date: return None
        t = timezone.localdate()
        return t.year - o.birth_date.year - ((t.month, t.day) < (o.birth_date.month, o.birth_date.day))


class PatientSelfSerializer(PatientSerializer):
    """Bemor o'z kartasida klinik bog'lanishlarni (poliklinika, shifokor) o'zgartira olmaydi."""
    class Meta(PatientSerializer.Meta):
        read_only_fields = ['card_no', 'user', 'polyclinic', 'family_doctor', 'pinfl']


class FamilySerializer(serializers.ModelSerializer):
    class Meta: model = m.FamilyMember; fields = '__all__'; read_only_fields = ['owner']


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta: model = m.Schedule; fields = '__all__'


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.full_name', read_only=True)
    specialization = serializers.CharField(source='doctor.specialization.name', read_only=True)
    room = serializers.CharField(source='doctor.room', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = m.Appointment
        fields = ['id', 'patient', 'patient_name', 'family_member', 'doctor', 'doctor_name', 'specialization', 'room',
                  'date', 'time', 'status', 'status_label', 'reason', 'cancel_reason', 'created_at']
        read_only_fields = ['patient', 'status', 'cancel_reason', 'created_at']

    def validate(self, d):
        from .services import free_slots
        doctor, date, time = d['doctor'], d['date'], d['time']
        if not doctor.is_active:
            raise serializers.ValidationError('Shifokor faol emas')
        if date < timezone.localdate():
            raise serializers.ValidationError({'date': 'O\'tgan sanaga yozilib bo\'lmaydi'})
        if time not in free_slots(doctor, date):
            raise serializers.ValidationError({'time': 'Bu vaqt band yoki ish jadvalida yo\'q'})
        return d


class TicketSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.user.full_name', read_only=True)
    room = serializers.CharField(source='doctor.room', read_only=True)
    patient_name = serializers.CharField(source='patient.user.full_name', read_only=True)
    info = serializers.SerializerMethodField()
    class Meta:
        model = m.QueueTicket
        fields = ['id', 'doctor', 'doctor_name', 'room', 'patient', 'patient_name', 'date', 'number', 'status',
                  'notify_before', 'created_at', 'info']
        read_only_fields = fields
    def get_info(self, o): return queue_info(o)


class ICDSerializer(serializers.ModelSerializer):
    class Meta: model = m.ICD10; fields = '__all__'


class RecordSerializer(serializers.ModelSerializer):
    diagnosis_text = serializers.CharField(source='diagnosis', read_only=True, default='')
    doctor_name = serializers.CharField(source='doctor.user.full_name', read_only=True)
    class Meta:
        model = m.MedicalRecord
        fields = ['id', 'patient', 'doctor', 'doctor_name', 'appointment', 'complaint', 'objective', 'diagnosis',
                  'diagnosis_text', 'recommendations', 'created_at']
        read_only_fields = ['doctor', 'created_at']


class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta: model = m.PrescriptionItem; fields = ['id', 'medicine', 'dose', 'times_per_day', 'days']


class PrescriptionSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True)
    doctor_name = serializers.CharField(source='doctor.user.full_name', read_only=True)
    class Meta:
        model = m.Prescription
        fields = ['id', 'number', 'patient', 'doctor', 'doctor_name', 'valid_until', 'created_at', 'items']
        read_only_fields = ['number', 'doctor', 'created_at']
    def create(self, d):
        items = d.pop('items')
        p = m.Prescription.objects.create(**d)
        for i in items: m.PrescriptionItem.objects.create(prescription=p, **i)
        return p


class LabResultSerializer(serializers.ModelSerializer):
    flag = serializers.CharField(read_only=True)
    class Meta: model = m.LabResult; fields = '__all__'


class LabOrderSerializer(serializers.ModelSerializer):
    class Meta: model = m.LabOrder; fields = '__all__'; read_only_fields = ['patient', 'status', 'created_at']


class MetricSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    class Meta: model = m.HealthMetric; fields = '__all__'; read_only_fields = ['patient']


class ReminderSerializer(serializers.ModelSerializer):
    taken_today = serializers.SerializerMethodField()
    class Meta: model = m.MedicationReminder; fields = '__all__'; read_only_fields = ['patient']
    def get_taken_today(self, o):
        return o.logs.filter(date=timezone.localdate(), taken=True).exists()


class VaccinationSerializer(serializers.ModelSerializer):
    class Meta: model = m.Vaccination; fields = '__all__'; read_only_fields = ['patient']


class ReviewSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.user.first_name', read_only=True)
    class Meta:
        model = m.Review
        fields = ['id', 'author_name', 'doctor', 'place', 'rating', 'text', 'created_at']
        read_only_fields = ['created_at']
    def validate_rating(self, v):
        if not 1 <= v <= 5: raise serializers.ValidationError('1 dan 5 gacha')
        return v
    def validate(self, d):
        if bool(d.get('doctor')) == bool(d.get('place')):
            raise serializers.ValidationError('Shifokor yoki muassasadan bittasini tanlang')
        return d
