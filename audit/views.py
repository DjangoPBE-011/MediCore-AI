from rest_framework import serializers, viewsets
from accounts.permissions import IsAdmin
from .models import AuditLog


class AuditSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True, default='')
    class Meta:
        model = AuditLog
        fields = ['id', 'created_at', 'user', 'user_name', 'role', 'action', 'object_type', 'object_id', 'detail', 'ip']


class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    """Faqat o'qish: admin jurnalni o'zgartira olmaydi."""
    permission_classes = [IsAdmin]
    serializer_class = AuditSerializer
    queryset = AuditLog.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        for f in ('action', 'role', 'object_type'):
            if p.get(f): qs = qs.filter(**{f: p[f]})
        if p.get('user'): qs = qs.filter(user_id=p['user'])
        return qs
