from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger'),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('clinic.urls')),
    path('api/', include('certs.urls')),
    path('api/', include('catalog.urls')),
    path('api/', include('audit.urls')),
    path('api/', include('notify.urls')),
    path('api/assistant/', include('assistant.urls')),
]
