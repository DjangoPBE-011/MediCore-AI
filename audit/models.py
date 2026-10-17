from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """O'zgarmas jurnal. Parol va tokenlar hech qachon yozilmaydi."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    role = models.CharField(max_length=10, blank=True)
    action = models.CharField(max_length=60, db_index=True)
    object_type = models.CharField(max_length=60, blank=True)
    object_id = models.CharField(max_length=40, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
