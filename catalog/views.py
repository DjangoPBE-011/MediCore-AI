from math import asin, cos, radians, sin, sqrt
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from accounts.permissions import IsAdminOrReadOnly
from audit.utils import log
from . import models as m
from . import serializers as s


class _Catalog(viewsets.ModelViewSet):
    """Hamma o'qiy oladi, faqat admin boshqaradi (o'chirish o'rniga is_active=False)."""
    permission_classes = [IsAdminOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = self.queryset
        if self.request.user.role != 'admin':
            qs = qs.filter(is_active=True)
        q = self.request.query_params.get('q')
        if q: qs = qs.filter(name__icontains=q)
        return qs

    def perform_create(self, ser):
        o = ser.save(); log(self.request, f'{o.__class__.__name__.lower()}_create', o, {})

    def perform_update(self, ser):
        o = ser.save(); log(self.request, f'{o.__class__.__name__.lower()}_update', o, {})


class MedicineViewSet(_Catalog):
    queryset = m.Medicine.objects.all().order_by('-id'); serializer_class = s.MedicineSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get('category'): qs = qs.filter(category=p['category'])
        if p.get('discounted'):
            qs = qs.filter(old_price__isnull=False).filter(Q(discount_until__isnull=True) | Q(discount_until__gte=timezone.localdate()))
        return qs


class DeviceViewSet(_Catalog):
    queryset = m.HealthDevice.objects.all().order_by('-id'); serializer_class = s.DeviceSerializer
    def get_queryset(self):
        qs = super().get_queryset(); c = self.request.query_params.get('category')
        return qs.filter(category=c) if c else qs


class SanatoriumViewSet(_Catalog):
    queryset = m.Sanatorium.objects.all().order_by('-rating'); serializer_class = s.SanatoriumSerializer


def _hav(lat1, lng1, lat2, lng2):
    la1, la2 = radians(lat1), radians(lat2)
    a = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin(radians(lng2 - lng1) / 2) ** 2
    return int(2 * 6371000 * asin(sqrt(a)))


class PlaceViewSet(_Catalog):
    queryset = m.Place.objects.all().order_by('id'); serializer_class = s.PlaceSerializer

    def list(self, request, *a, **kw):
        qs = self.get_queryset()
        kind = request.query_params.get('kind')
        if kind: qs = qs.filter(kind=kind)
        data = s.PlaceSerializer(qs, many=True).data
        try:
            lat, lng = float(request.query_params['lat']), float(request.query_params['lng'])
            for d in data:
                d['distance_m'] = _hav(lat, lng, float(d['lat']), float(d['lng']))
            data.sort(key=lambda d: d['distance_m'])
        except (KeyError, ValueError):
            pass
        return Response(data)
