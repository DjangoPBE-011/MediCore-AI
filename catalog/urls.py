from rest_framework.routers import DefaultRouter
from . import views as v
r = DefaultRouter()
r.register('medicines', v.MedicineViewSet, 'medicines')
r.register('places', v.PlaceViewSet, 'places')
r.register('devices', v.DeviceViewSet, 'devices')
r.register('sanatoriums', v.SanatoriumViewSet, 'sanatoriums')
urlpatterns = r.urls
