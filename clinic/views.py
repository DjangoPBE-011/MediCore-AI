from datetime import date as date_cls, datetime, timedelta
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsAdmin, IsAdminOrReadOnly, IsDoctor, IsPatient
from audit.utils import log
from notify.services import notify
from . import models as m
from . import serializers as s
from .services import free_slots


def _patient(request):
    p = getattr(request.user, 'patient', None)
    if not p: raise PermissionDenied('Bemor profili yo\'q')
    return p


def _doctor(request):
    d = getattr(request.user, 'doctor', None)
    if not d: raise PermissionDenied('Shifokor profili yo\'q')
    return d


class PolyclinicViewSet(viewsets.ModelViewSet):
    queryset = m.Polyclinic.objects.all().order_by('id')
    serializer_class = s.PolyclinicSerializer
    permission_classes = [IsAdminOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


class SpecializationViewSet(viewsets.ModelViewSet):
    queryset = m.Specialization.objects.all().order_by('id')
    serializer_class = s.SpecializationSerializer
    permission_classes = [IsAdminOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


class DoctorViewSet(viewsets.ModelViewSet):
    """O'chirish yo'q: shifokor faqat faolsizlantiriladi."""
    permission_classes = [IsAdminOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        return s.DoctorCreateSerializer if self.action == 'create' else s.DoctorSerializer

    def get_queryset(self):
        qs = m.Doctor.objects.select_related('user', 'polyclinic', 'specialization').order_by('id')
        if self.request.user.role != 'admin':
            qs = qs.filter(is_active=True)
        p = self.request.query_params
        if p.get('specialization'): qs = qs.filter(specialization_id=p['specialization'])
        if p.get('polyclinic'): qs = qs.filter(polyclinic_id=p['polyclinic'])
        if p.get('q'): qs = qs.filter(Q(user__last_name__icontains=p['q']) | Q(user__first_name__icontains=p['q']))
        return qs

    def create(self, request, *a, **kw):
        ser = s.DoctorCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.save()
        log(request, 'doctor_create', d, {'username': d.user.username})
        return Response(s.DoctorSerializer(d).data, status=201)

    def perform_update(self, ser):
        d = ser.save()
        d.user.is_active = d.is_active  # faolsizlantirilsa kira olmaydi
        d.user.save(update_fields=['is_active'])
        log(self.request, 'doctor_update', d, {'is_active': d.is_active})

    @action(detail=True, methods=['get'])
    def slots(self, request, pk=None):
        d = self.get_object()
        try:
            day = date_cls.fromisoformat(request.query_params.get('date', ''))
        except ValueError:
            raise ValidationError({'date': 'YYYY-MM-DD'})
        return Response({'date': day, 'slots': [t.strftime('%H:%M') for t in free_slots(d, day)]})

    @action(detail=True, methods=['get', 'put'], permission_classes=[IsAdmin])
    def schedule(self, request, pk=None):
        d = self.get_object()
        if request.method == 'PUT':
            m.Schedule.objects.filter(doctor=d).delete()
            for row in request.data:
                ser = s.ScheduleSerializer(data={**row, 'doctor': d.pk}); ser.is_valid(raise_exception=True); ser.save()
            log(request, 'schedule_update', d, {'rows': len(request.data)})
        return Response(s.ScheduleSerializer(d.schedules.all(), many=True).data)


class PatientViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        return s.PatientSerializer

    def get_permissions(self):
        if self.action in ('create', 'partial_update', 'update'):
            return [IsAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        u = self.request.user
        qs = m.Patient.objects.select_related('user').order_by('id')
        if u.role == 'patient':
            qs = qs.filter(user=u)
        elif u.role == 'doctor':
            d = _doctor(self.request)
            qs = qs.filter(Q(polyclinic=d.polyclinic) | Q(appointments__doctor=d) | Q(tickets__doctor=d)).distinct()
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(Q(user__last_name__icontains=q) | Q(user__first_name__icontains=q) |
                           Q(card_no__icontains=q) | Q(pinfl__icontains=q))
        return qs

    def retrieve(self, request, *a, **kw):
        resp = super().retrieve(request, *a, **kw)
        if request.user.role == 'doctor':
            log(request, 'patient_view', self.get_object(), {})
        return resp

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        p = _patient(request)
        if request.method == 'PATCH':
            ser = s.PatientSelfSerializer(p, data=request.data, partial=True)
            ser.is_valid(raise_exception=True); ser.save()
            log(request, 'profile_update', p, {'fields': list(request.data.keys())})
        return Response(s.PatientSelfSerializer(p).data)


class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = s.AppointmentSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        u = self.request.user
        qs = m.Appointment.objects.select_related('patient__user', 'doctor__user', 'doctor__specialization').order_by('date', 'time')
        if u.role == 'patient': qs = qs.filter(patient__user=u)
        elif u.role == 'doctor': qs = qs.filter(doctor__user=u)
        p = self.request.query_params
        if p.get('status'): qs = qs.filter(status=p['status'])
        if p.get('date'): qs = qs.filter(date=p['date'])
        if p.get('today'): qs = qs.filter(date=timezone.localdate())
        return qs

    def create(self, request, *a, **kw):
        if request.user.role != 'patient':
            raise PermissionDenied('Faqat bemor qabulga yozila oladi')
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        p = _patient(request)
        dup = m.Appointment.objects.filter(patient=p, date=ser.validated_data['date'], time=ser.validated_data['time'],
                                           status__in=m.Appointment.ACTIVE).exists()
        if dup:
            raise ValidationError('Shu vaqtga allaqachon yozilgansiz')
        try:
            with transaction.atomic():
                a = ser.save(patient=p)
        except IntegrityError:
            raise ValidationError({'time': 'Bu vaqt band qilib bo\'lingan'})
        log(request, 'appointment_create', a, {'doctor': a.doctor_id, 'date': str(a.date), 'time': str(a.time)})
        notify(a.doctor.user, 'Yangi qabul', f'{p.user.full_name} · {a.date} {a.time:%H:%M}', 'appointment')
        return Response(self.get_serializer(a).data, status=201)

    def _set(self, request, allowed, new, who):
        a = self.get_object()
        if request.user.role not in who:
            raise PermissionDenied('Ruxsat yo\'q')
        if a.status not in allowed:
            raise ValidationError(f'"{a.get_status_display()}" holatidan o\'tish mumkin emas')
        a.status = new
        return a

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        a = self._set(request, ('pending',), 'confirmed', ('doctor',)); a.save()
        notify(a.patient.user, 'Qabul tasdiqlandi', f'{a.date} {a.time:%H:%M}', 'appointment')
        log(request, 'appointment_confirm', a, {}); return Response(self.get_serializer(a).data)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        a = self._set(request, ('confirmed',), 'in_progress', ('doctor',)); a.save()
        log(request, 'appointment_start', a, {}); return Response(self.get_serializer(a).data)

    @action(detail=True, methods=['post'])
    def finish(self, request, pk=None):
        a = self._set(request, ('in_progress',), 'done', ('doctor',)); a.save()
        log(request, 'appointment_finish', a, {}); return Response(self.get_serializer(a).data)

    @action(detail=True, methods=['post'])
    def no_show(self, request, pk=None):
        a = self._set(request, ('confirmed', 'pending'), 'no_show', ('doctor',)); a.save()
        log(request, 'appointment_no_show', a, {}); return Response(self.get_serializer(a).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        a = self._set(request, ('pending', 'confirmed'), 'cancelled', ('doctor', 'patient'))
        if request.user.role == 'patient':
            start = timezone.make_aware(datetime.combine(a.date, a.time))
            if start - timezone.now() < timedelta(hours=2):
                raise ValidationError('Qabulga 2 soatdan kam qolganda bekor qilib bo\'lmaydi')
        a.cancel_reason = request.data.get('reason', '')
        a.save()
        other = a.doctor.user if request.user.role == 'patient' else a.patient.user
        notify(other, 'Qabul bekor qilindi', f'{a.date} {a.time:%H:%M}', 'appointment')
        log(request, 'appointment_cancel', a, {'by': request.user.role})
        return Response(self.get_serializer(a).data)


class QueueViewSet(viewsets.GenericViewSet):
    """Onlayn navbat."""
    serializer_class = s.TicketSerializer

    @action(detail=False, methods=['post'], permission_classes=[IsPatient])
    def take(self, request):
        doc = get_object_or_404(m.Doctor, pk=request.data.get('doctor'), is_active=True)
        p, today = _patient(request), timezone.localdate()
        with transaction.atomic():
            if m.QueueTicket.objects.filter(doctor=doc, patient=p, date=today, status__in=['waiting', 'called']).exists():
                raise ValidationError('Sizda bu shifokorga navbat bor')
            last = (m.QueueTicket.objects.select_for_update().filter(doctor=doc, date=today)
                    .order_by('-number').first())
            t = m.QueueTicket.objects.create(doctor=doc, patient=p, date=today, number=(last.number + 1) if last else 1,
                                             notify_before=int(request.data.get('notify_before', 2)))
        log(request, 'queue_take', t, {'doctor': doc.pk, 'number': t.number})
        return Response(s.TicketSerializer(t).data, status=201)

    @action(detail=False, methods=['get'], permission_classes=[IsPatient])
    def my(self, request):
        qs = m.QueueTicket.objects.filter(patient=_patient(request), date=timezone.localdate(),
                                          status__in=['waiting', 'called'])
        return Response(s.TicketSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], permission_classes=[IsPatient])
    def cancel(self, request, pk=None):
        t = get_object_or_404(m.QueueTicket, pk=pk, patient=_patient(request), status='waiting')
        t.status = 'cancelled'; t.save()
        return Response(s.TicketSerializer(t).data)

    @action(detail=False, methods=['get'], permission_classes=[IsDoctor])
    def board(self, request):
        d = _doctor(request); today = timezone.localdate()
        qs = m.QueueTicket.objects.filter(doctor=d, date=today).select_related('patient__user')
        cur = qs.filter(status='called').first()
        return Response({
            'current': s.TicketSerializer(cur).data if cur else None,
            'waiting': s.TicketSerializer(qs.filter(status='waiting'), many=True).data,
            'stats': {'waiting': qs.filter(status='waiting').count(), 'done': qs.filter(status='done').count(),
                      'total': qs.count()},
        })

    @action(detail=False, methods=['post'], permission_classes=[IsDoctor])
    def call_next(self, request):
        d = _doctor(request); today = timezone.localdate()
        with transaction.atomic():
            m.QueueTicket.objects.filter(doctor=d, date=today, status='called').update(status='done')
            nxt = m.QueueTicket.objects.select_for_update().filter(doctor=d, date=today, status='waiting').order_by('number').first()
            if not nxt:
                return Response({'current': None, 'detail': 'Navbat bo\'sh'})
            nxt.status = 'called'; nxt.called_at = timezone.now(); nxt.save()
        notify(nxt.patient.user, 'Sizning navbatingiz', f'№{nxt.number}: {d.room}-xonaga kiring', 'queue')
        # "N kishi qolganda xabar ber"
        for t in m.QueueTicket.objects.filter(doctor=d, date=today, status='waiting', notified=False).order_by('number'):
            ahead = m.QueueTicket.objects.filter(doctor=d, date=today, status='waiting', number__lt=t.number).count()
            if ahead <= t.notify_before:
                notify(t.patient.user, 'Navbatingiz yaqinlashdi', f'Oldingizda {ahead} kishi', 'queue')
                t.notified = True; t.save(update_fields=['notified'])
        log(request, 'queue_call_next', nxt, {'number': nxt.number})
        return Response({'current': s.TicketSerializer(nxt).data})

    @action(detail=False, methods=['get'])
    def doctors(self, request):
        """Bemor uchun: shifokorlar va ularning bugungi navbat uzunligi."""
        today = timezone.localdate()
        qs = (m.Doctor.objects.filter(is_active=True).select_related('user', 'specialization')
              .annotate(q=Count('tickets', filter=Q(tickets__date=today, tickets__status='waiting'))))
        return Response([{'id': d.id, 'full_name': d.user.full_name, 'specialization': d.specialization.name,
                          'room': d.room, 'waiting': d.q, 'eta_minutes': d.q * d.specialization.slot_minutes} for d in qs])


class ICDViewSet(viewsets.ModelViewSet):
    serializer_class = s.ICDSerializer
    permission_classes = [IsAdminOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    def get_queryset(self):
        qs = m.ICD10.objects.all()
        if self.request.user.role != 'admin': qs = qs.filter(is_active=True)
        q = self.request.query_params.get('q')
        if q: qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        return qs


class _OwnedMixin:
    """Bemorga tegishli yozuvlar: bemor o'zinikini ko'radi."""
    def patient_qs(self, model):
        u = self.request.user
        qs = model.objects.all()
        if u.role == 'patient': return qs.filter(patient__user=u)
        if u.role == 'doctor':
            d = _doctor(self.request)
            return qs.filter(Q(patient__polyclinic=d.polyclinic) | Q(patient__appointments__doctor=d)).distinct()
        return qs


class RecordViewSet(_OwnedMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Ko'rik natijalari: shifokor yozadi, bemor faqat o'qiydi."""
    serializer_class = s.RecordSerializer
    def get_queryset(self):
        qs = self.patient_qs(m.MedicalRecord)
        if self.request.query_params.get('patient'): qs = qs.filter(patient_id=self.request.query_params['patient'])
        return qs.select_related('diagnosis', 'doctor__user')
    def create(self, request, *a, **kw):
        if request.user.role != 'doctor': raise PermissionDenied('Faqat shifokor')
        return super().create(request, *a, **kw)
    def perform_create(self, ser):
        r = ser.save(doctor=_doctor(self.request))
        log(self.request, 'record_create', r, {'patient': r.patient_id, 'diagnosis': str(r.diagnosis or '')})


class PrescriptionViewSet(_OwnedMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = s.PrescriptionSerializer
    def get_queryset(self): return self.patient_qs(m.Prescription).prefetch_related('items')
    def create(self, request, *a, **kw):
        if request.user.role != 'doctor': raise PermissionDenied('Faqat shifokor')
        return super().create(request, *a, **kw)
    def perform_create(self, ser):
        p = ser.save(doctor=_doctor(self.request)); log(self.request, 'prescription_create', p, {})
        notify(p.patient.user, 'Yangi retsept', p.number, 'prescription')


class LabResultViewSet(_OwnedMixin, mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = s.LabResultSerializer
    def get_queryset(self):
        qs = self.patient_qs(m.LabResult)
        p = self.request.query_params
        if p.get('indicator'): qs = qs.filter(indicator=p['indicator'])
        if p.get('patient') and self.request.user.role != 'patient': qs = qs.filter(patient_id=p['patient'])
        return qs
    def create(self, request, *a, **kw):
        if request.user.role == 'patient': raise PermissionDenied('Natijani laboratoriya/shifokor kiritadi')
        return super().create(request, *a, **kw)


class _PatientOwned(viewsets.ModelViewSet):
    """Bemor o'z ma'lumotlarini boshqaradi (kundalik, eslatma, emlash...)."""
    permission_classes = [IsPatient]
    def get_queryset(self):
        return self.queryset.filter(patient=_patient(self.request))
    def perform_create(self, ser):
        ser.save(patient=_patient(self.request))


class LabOrderViewSet(_PatientOwned):
    queryset = m.LabOrder.objects.all(); serializer_class = s.LabOrderSerializer
    http_method_names = ['get', 'post', 'head', 'options']


class MetricViewSet(_PatientOwned):
    queryset = m.HealthMetric.objects.all(); serializer_class = s.MetricSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        k = self.request.query_params.get('kind')
        return qs.filter(kind=k) if k else qs


class ReminderViewSet(_PatientOwned):
    queryset = m.MedicationReminder.objects.all(); serializer_class = s.ReminderSerializer
    @action(detail=True, methods=['post'])
    def take(self, request, pk=None):
        r = self.get_object()
        m.ReminderLog.objects.update_or_create(reminder=r, date=timezone.localdate(), defaults={'taken': True})
        return Response(self.get_serializer(r).data)


class VaccinationViewSet(_PatientOwned):
    queryset = m.Vaccination.objects.all(); serializer_class = s.VaccinationSerializer


class FamilyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsPatient]
    serializer_class = s.FamilySerializer
    def get_queryset(self): return m.FamilyMember.objects.filter(owner=_patient(self.request))
    def perform_create(self, ser): ser.save(owner=_patient(self.request))


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = s.ReviewSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    def get_queryset(self):
        qs = m.Review.objects.select_related('author__user')
        p = self.request.query_params
        if p.get('doctor'): qs = qs.filter(doctor_id=p['doctor'])
        if p.get('place'): qs = qs.filter(place_id=p['place'])
        return qs
    def create(self, request, *a, **kw):
        if request.user.role != 'patient': raise PermissionDenied('Faqat bemor sharh yozadi')
        return super().create(request, *a, **kw)
    def perform_create(self, ser):
        p = _patient(self.request)
        doc = ser.validated_data.get('doctor')
        if doc and not m.Appointment.objects.filter(patient=p, doctor=doc, status='done').exists():
            raise ValidationError('Sharh faqat qabuldan keyin yoziladi')
        ser.save(author=p)


class StatsView(APIView):
    """Admin dashboard va hisobotlar; shifokor uchun o'z statistikasi."""
    def get(self, request):
        today = timezone.localdate()
        if request.user.role == 'doctor':
            d = _doctor(request)
            a = m.Appointment.objects.filter(doctor=d, date=today)
            return Response({'today': a.count(), 'waiting': a.filter(status__in=['pending', 'confirmed']).count(),
                             'done': a.filter(status='done').count(), 'cancelled': a.filter(status='cancelled').count(),
                             'draft_certificates': d.certificates.filter(status='draft').count(),
                             'pending_certificates': d.certificates.filter(status='pending').count()})
        if request.user.role != 'admin':
            raise PermissionDenied()
        from certs.models import Certificate
        by_status = dict(Certificate.objects.values_list('status').annotate(c=Count('id')))
        top_doctors = list(m.Appointment.objects.filter(date__month=today.month, date__year=today.year)
                           .values('doctor__user__last_name', 'doctor__user__first_name')
                           .annotate(c=Count('id')).order_by('-c')[:5])
        top_dx = list(m.MedicalRecord.objects.exclude(diagnosis=None).values('diagnosis__code', 'diagnosis__name')
                      .annotate(c=Count('id')).order_by('-c')[:5])
        return Response({
            'patients': m.Patient.objects.count(), 'doctors': m.Doctor.objects.filter(is_active=True).count(),
            'polyclinics': m.Polyclinic.objects.filter(is_active=True).count(),
            'appointments_today': m.Appointment.objects.filter(date=today).count(),
            'certificates_by_status': by_status, 'top_doctors': top_doctors, 'top_diagnoses': top_dx,
            'cancel_rate': round(100 * m.Appointment.objects.filter(status='cancelled').count() /
                                 max(1, m.Appointment.objects.count()), 1),
        })
