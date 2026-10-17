from rest_framework.permissions import BasePermission, SAFE_METHODS


class _Role(BasePermission):
    role = None
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.role == self.role)


class IsAdmin(_Role): role = 'admin'
class IsDoctor(_Role): role = 'doctor'
class IsPatient(_Role): role = 'patient'


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        return request.method in SAFE_METHODS or u.role == 'admin'
