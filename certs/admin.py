from django.contrib import admin
from .models import Certificate

@admin.register(Certificate)
class C(admin.ModelAdmin):
    list_display = ('number', 'patient', 'doctor', 'status')
    readonly_fields = [f.name for f in Certificate._meta.fields]
    def has_add_permission(self, r): return False
    def has_change_permission(self, r, o=None): return False
    def has_delete_permission(self, r, o=None): return False
