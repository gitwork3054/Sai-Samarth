from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("auth/", include("allauth.urls")),
    path("", include("travel.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Sai Samarth Holidays · Owner Console"
admin.site.site_title = "Sai Samarth Holidays Admin"
admin.site.index_title = "Manage packages, pricing, itineraries and enquiries"
