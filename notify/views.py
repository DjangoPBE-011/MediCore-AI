from rest_framework import mixins, serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsAdmin
from .models import DeviceToken, Notification
from .services import notify


class NSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'kind', 'is_read', 'created_at']
        read_only_fields = ['title', 'body', 'kind', 'created_at']


class NotificationViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = NSerializer
    http_method_names = ['get', 'patch', 'post', 'head', 'options']
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def read_all(self, request):
        self.get_queryset().update(is_read=True)
        return Response({'ok': True})


class DeviceTokenView(APIView):
    def post(self, request):
        t = request.data.get('token')
        if not t:
            return Response({'token': 'majburiy'}, status=400)
        DeviceToken.objects.update_or_create(token=t, defaults={'user': request.user, 'platform': request.data.get('platform', 'android')})
        return Response({'ok': True})


class BroadcastView(APIView):
    """Admin: ommaviy xabar."""
    permission_classes = [IsAdmin]
    def post(self, request):
        from django.contrib.auth import get_user_model
        U = get_user_model()
        audience = request.data.get('audience', 'all')
        qs = U.objects.filter(is_active=True)
        if audience in ('doctor', 'patient'):
            qs = qs.filter(role=audience)
        n = 0
        for u in qs:
            notify(u, request.data.get('title', ''), request.data.get('body', ''), 'broadcast'); n += 1
        from audit.utils import log
        log(request, 'broadcast', None, {'audience': audience, 'count': n})
        return Response({'sent': n})
