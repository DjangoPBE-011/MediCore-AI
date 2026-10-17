from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class MeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'phone', 'first_name', 'last_name', 'middle_name',
                  'full_name', 'role', 'language', 'two_factor']
        read_only_fields = ['id', 'username', 'role']


class UserAdminSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])
    full_name = serializers.CharField(read_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'phone', 'first_name', 'last_name', 'middle_name', 'full_name',
                  'role', 'is_active', 'last_login', 'password']
        read_only_fields = ['last_login']

    def create(self, validated):
        pw = validated.pop('password', None)
        u = User(**validated)
        u.set_password(pw) if pw else u.set_unusable_password()
        u.save()
        return u

    def update(self, inst, validated):
        pw = validated.pop('password', None)
        for k, v in validated.items():
            setattr(inst, k, v)
        if pw:
            inst.set_password(pw)
        inst.save()
        return inst


class RegisterSerializer(serializers.Serializer):
    """Faqat bemorlar o'zlari ro'yxatdan o'tadi. Rol har doim 'patient'."""
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)

    def validate_phone(self, v):
        v = ''.join(c for c in v if c.isdigit() or c == '+')
        if User.objects.filter(username=v).exists():
            raise serializers.ValidationError('Bu telefon raqam band')
        return v

    def create(self, d):
        u = User.objects.create_user(username=d['phone'], phone=d['phone'], password=d['password'],
                                     first_name=d['first_name'], last_name=d['last_name'], role='patient')
        from clinic.models import Patient
        Patient.objects.create(user=u)
        return u


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = MeSerializer(self.user).data
        return data
