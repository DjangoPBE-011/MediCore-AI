from rest_framework import serializers
from . import models as m


class MedicineSerializer(serializers.ModelSerializer):
    discount_percent = serializers.IntegerField(read_only=True)
    class Meta: model = m.Medicine; fields = '__all__'


class PlaceSerializer(serializers.ModelSerializer):
    distance_m = serializers.IntegerField(read_only=True, required=False)
    class Meta: model = m.Place; fields = '__all__'


class DeviceSerializer(serializers.ModelSerializer):
    discount_percent = serializers.SerializerMethodField()
    class Meta: model = m.HealthDevice; fields = '__all__'
    def get_discount_percent(self, o):
        return round((1 - o.price / o.old_price) * 100) if o.old_price and o.old_price > o.price else 0


class SanatoriumSerializer(serializers.ModelSerializer):
    class Meta: model = m.Sanatorium; fields = '__all__'
