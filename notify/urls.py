from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, DeviceTokenView, BroadcastView
router = DefaultRouter()
router.register('notifications', NotificationViewSet, basename='notifications')
urlpatterns = router.urls + [
    path('device-token/', DeviceTokenView.as_view()),
    path('broadcast/', BroadcastView.as_view()),
]
