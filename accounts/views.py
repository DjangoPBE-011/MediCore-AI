from django.contrib.auth import get_user_model
from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from audit.utils import log
from .permissions import IsAdmin
from .serializers import (LoginSerializer, MeSerializer, PasswordChangeSerializer,
                          RegisterSerializer, UserAdminSerializer)

User = get_user_model()


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_scope = 'login'

    def post(self, request, *a, **kw):
        resp = super().post(request, *a, **kw)
        # parol va token auditga YOZILMAYDI
        log(request, 'login' if resp.status_code == 200 else 'login_failed', None,
            {'username': str(request.data.get('username', ''))}, user=None if resp.status_code != 200 else User.objects.filter(username=request.data.get('username')).first())
        return resp


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'login'

    def create(self, request, *a, **kw):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        u = s.save()
        log(request, 'register', u, {'role': 'patient'}, user=u)
        return Response(MeSerializer(u).data, status=201)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer
    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    def post(self, request):
        s = PasswordChangeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if not request.user.check_password(s.validated_data['old_password']):
            return Response({'old_password': 'Noto\'g\'ri parol'}, status=400)
        request.user.set_password(s.validated_data['new_password'])
        request.user.save()
        log(request, 'password_changed', request.user, {})
        return Response({'ok': True})


class UserAdminViewSet(viewsets.ModelViewSet):
    """Admin: foydalanuvchilar. O'chirish yo'q, faqat faolsizlantirish."""
    permission_classes = [IsAdmin]
    serializer_class = UserAdminSerializer
    queryset = User.objects.all().order_by('-date_joined')
    filterset_fields = ['role', 'is_active']
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get('role')
        q = self.request.query_params.get('q')
        if role: qs = qs.filter(role=role)
        if q: qs = qs.filter(username__icontains=q) | qs.filter(last_name__icontains=q)
        return qs

    def perform_create(self, s):
        u = s.save(); log(self.request, 'user_create', u, {'role': u.role})

    def perform_update(self, s):
        u = s.save(); log(self.request, 'user_update', u, {'fields': list(s.validated_data.keys() - {'password'})})
