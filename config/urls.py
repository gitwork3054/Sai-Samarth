from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from accounts.views import confirm_sms, SMSLoginView, SMSSignupView

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("auth/phone/verify/", confirm_sms, name="sms_confirm"),
    path("auth/login/", SMSLoginView.as_view(), name="sms_account_login"),
    path("auth/signup/", SMSSignupView.as_view(), name="sms_account_signup"),
    path("auth/", include("allauth.urls")),
    path("", include("travel.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Sai Samarth Holidays · Owner Console"
admin.site.site_title = "Sai Samarth Holidays Admin"
admin.site.index_title = "Manage packages, pricing, itineraries and enquiries"
