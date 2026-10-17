from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views
router = DefaultRouter()
router.register('certificates', views.CertificateViewSet, basename='certificates')
router.register('shares', views.ShareViewSet, basename='shares')
urlpatterns = router.urls + [
    path('verify/<str:token>/', views.VerifyView.as_view()),
    path('shared/<str:token>/', views.SharedView.as_view()),
]
