from rest_framework import serializers
from .models import Certificate, ShareLink


class CertificateSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.user.full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.full_name', read_only=True)
    diagnosis_text = serializers.CharField(source='diagnosis', read_only=True, default='')
    effective_status = serializers.CharField(read_only=True)
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = ['id', 'number', 'patient', 'patient_name', 'doctor', 'doctor_name', 'kind', 'conclusion',
                  'diagnosis', 'diagnosis_text', 'valid_until', 'status', 'effective_status', 'status_label',
                  'reject_reason', 'cancel_reason', 'signature_serial', 'signed_at', 'qr_token', 'created_at']
        read_only_fields = ['number', 'doctor', 'status', 'reject_reason', 'cancel_reason',
                            'signature_serial', 'signed_at', 'qr_token', 'created_at']

    def get_status_label(self, o):
        return dict(Certificate.S.choices).get(o.effective_status, o.effective_status)

    def to_representation(self, inst):
        d = super().to_representation(inst)
        # bemorga qoralama/kutilayotgan hujjat va tashxis ko'rsatilmaydi (ko'rsatiladigani faqat tasdiqlangan)
        return d


class ShareSerializer(serializers.ModelSerializer):
    hours = serializers.IntegerField(write_only=True, default=24, min_value=1, max_value=24 * 30)
    class Meta:
        model = ShareLink
        fields = ['id', 'certificate', 'token', 'show_conclusion', 'show_diagnosis', 'expires_at', 'hours']
        read_only_fields = ['token', 'expires_at']
