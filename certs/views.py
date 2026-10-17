from datetime import timedelta
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsAdmin
from audit.utils import log
from notify.services import notify
from .models import Certificate, ShareLink
from .pdf import build_pdf
from .serializers import CertificateSerializer, ShareSerializer


class CertificateViewSet(viewsets.ModelViewSet):
    """
    Doktor: yaratadi / tahrirlaydi (faqat qoralama) / tasdiqlashga yuboradi / tasdiqlaydi (ERI) / rad etadi.
    Bemor: faqat o'zining TASDIQLANGAN hujjatlarini ko'radi va PDF yuklaydi.
    Admin: faqat o'qiydi, tahrirlay olmaydi va shifokor nomidan tasdiqlay olmaydi.
    """
    serializer_class = CertificateSerializer
    filterset_fields = ['status', 'kind']

    def get_queryset(self):
        u = self.request.user
        qs = Certificate.objects.select_related('patient__user', 'doctor__user', 'diagnosis')
        if u.role == 'admin':
            pass
        elif u.role == 'doctor':
            qs = qs.filter(doctor__user=u)
        else:
            qs = qs.filter(patient__user=u).exclude(status__in=['draft', 'pending'])
        st = self.request.query_params.get('status')
        if st == 'expired':
            qs = qs.filter(status='approved', valid_until__lt=timezone.localdate())
        elif st:
            qs = qs.filter(status=st)
        return qs

    def _require_doctor(self):
        if self.request.user.role != 'doctor':
            raise PermissionDenied('Faqat shifokor bajara oladi')

    def create(self, request, *a, **kw):
        self._require_doctor()
        return super().create(request, *a, **kw)

    def perform_create(self, s):
        c = s.save(doctor=self.request.user.doctor)
        log(self.request, 'certificate_create', c, {'number': c.number})

    def update(self, request, *a, **kw):
        self._require_doctor()
        obj = self.get_object()
        if not obj.editable:
            raise ValidationError('Faqat qoralama yoki rad etilgan hujjat tahrirlanadi')
        resp = super().update(request, *a, **kw)
        log(request, 'certificate_update', obj, {})
        return resp

    def destroy(self, request, *a, **kw):
        return Response({'detail': 'Hujjat o\'chirilmaydi. Bekor qilish mumkin.'}, status=405)

    def _tr(self, request, allowed, new, action_name, **extra):
        self._require_doctor()
        c = self.get_object()
        if c.status not in allowed:
            raise ValidationError(f'"{c.get_status_display()}" holatidan bu amalni bajarib bo\'lmaydi')
        c.status = new
        for k, v in extra.items():
            setattr(c, k, v)
        c.save()
        log(request, action_name, c, {'number': c.number, 'to': new})
        return c

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        c = self._tr(request, ('draft', 'rejected'), 'pending', 'certificate_submit', reject_reason='')
        return Response(self.get_serializer(c).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """ERI bilan tasdiqlash: imzo seriya raqami majburiy. Oddiy tugma ERI emas."""
        serial = (request.data.get('signature_serial') or '').strip()
        if not serial:
            raise ValidationError({'signature_serial': 'E-IMZO kalit seriya raqami majburiy'})
        c = self._tr(request, ('pending',), 'approved', 'certificate_approve',
                     signature_serial=serial, signature_data=request.data.get('signature_data', ''),
                     signed_at=timezone.now())
        notify(c.patient.user, 'Ma\'lumotnoma tayyor', f'{c.number} tasdiqlandi', 'certificate')
        return Response(self.get_serializer(c).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            raise ValidationError({'reason': 'Sabab majburiy'})
        c = self._tr(request, ('pending',), 'rejected', 'certificate_reject', reject_reason=reason)
        return Response(self.get_serializer(c).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        c = self._tr(request, ('draft', 'pending', 'approved', 'rejected'), 'cancelled', 'certificate_cancel',
                     cancel_reason=request.data.get('reason', ''))
        notify(c.patient.user, 'Ma\'lumotnoma bekor qilindi', c.number, 'certificate')
        return Response(self.get_serializer(c).data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        c = self.get_object()
        if c.status != 'approved':
            raise ValidationError('PDF faqat tasdiqlangan hujjat uchun')
        log(request, 'certificate_pdf', c, {'number': c.number})
        r = HttpResponse(build_pdf(c), content_type='application/pdf')
        r['Content-Disposition'] = f'attachment; filename="{c.number}.pdf"'
        return r


class VerifyView(APIView):
    """Ochiq QR tekshiruv. Faqat minimal ma'lumot: tashxis va tahlil KO'RSATILMAYDI."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'verify'

    def get(self, request, token):
        c = Certificate.objects.select_related('patient__user', 'doctor__polyclinic').filter(qr_token=token).first()
        if not c:
            return Response({'valid': False, 'reason': 'Topilmadi'}, status=404)
        st = c.effective_status
        u = c.patient.user
        masked = f'{u.last_name[:1]}. {u.first_name}'.strip()
        return Response({
            'valid': st == 'approved', 'status': st, 'status_label': dict(Certificate.S.choices)[st],
            'number': c.number, 'type': c.get_kind_display(), 'patient': masked,
            'valid_until': c.valid_until, 'organization': c.doctor.polyclinic.name,
        })


class ShareViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Bemor: ma'lumotnomani tanlab, vaqt bilan cheklab ulashadi."""
    serializer_class = ShareSerializer

    def get_queryset(self):
        return ShareLink.objects.filter(certificate__patient__user=self.request.user)

    def perform_create(self, s):
        cert = s.validated_data['certificate']
        if cert.patient.user_id != self.request.user.id or cert.status != 'approved':
            raise PermissionDenied('Faqat o\'zingizning tasdiqlangan hujjatingiz')
        hours = s.validated_data.pop('hours', 24)
        obj = s.save(expires_at=timezone.now() + timedelta(hours=hours))
        log(self.request, 'share_create', obj, {'cert': cert.number, 'hours': hours})


class SharedView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'verify'

    def get(self, request, token):
        s = get_object_or_404(ShareLink.objects.select_related('certificate__patient__user'), token=token)
        if not s.is_valid:
            return Response({'detail': 'Havola muddati tugagan'}, status=410)
        c = s.certificate
        data = {'number': c.number, 'type': c.get_kind_display(), 'patient': c.patient.user.full_name,
                'status': c.effective_status, 'valid_until': c.valid_until}
        if s.show_conclusion: data['conclusion'] = c.conclusion
        if s.show_diagnosis and c.diagnosis: data['diagnosis'] = str(c.diagnosis)
        return Response(data)
