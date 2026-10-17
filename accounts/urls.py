from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register('users', views.UserAdminViewSet, basename='users')
urlpatterns = [
    path('login/', views.LoginView.as_view()),
    path('refresh/', TokenRefreshView.as_view()),
    path('register/', views.RegisterView.as_view()),
    path('me/', views.MeView.as_view()),
    path('password/', views.PasswordChangeView.as_view()),
    path('', include(router.urls)),
]
