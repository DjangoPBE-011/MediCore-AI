from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class A(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'object_type', 'object_id')
    def has_add_permission(self, r): return False
    def has_change_permission(self, r, o=None): return False
    def has_delete_permission(self, r, o=None): return False
