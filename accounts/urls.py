from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("signup/", views.SMSSignupView.as_view(), name="signup"),
    path("login/", views.SMSLoginView.as_view(), name="login"),
    path("mobile/", views.enroll_mobile, name="enroll_mobile"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
]
