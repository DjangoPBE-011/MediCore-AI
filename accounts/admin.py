from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class U(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('MediCore', {'fields': ('role', 'phone', 'middle_name', 'language', 'two_factor')}),)
    list_display = ('username', 'role', 'last_name', 'first_name', 'is_active')
