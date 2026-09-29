from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("packages/", views.package_list, name="packages"),
    path("domestic/", views.package_list, {"preset": "domestic"}, name="domestic"),
    path("international/", views.package_list, {"preset": "international"}, name="international"),
    path("group-tours/", views.package_list, {"preset": "group"}, name="group_tours"),
    path("corporate-tours/", views.package_list, {"preset": "corporate"}, name="corporate_tours"),
    path("offers/", views.package_list, {"preset": "offers"}, name="offers"),
    path("events/", views.package_list, {"preset": "events"}, name="events"),
    path("photo-credits/", views.photo_credits, name="photo_credits"),
    path("package/<slug:slug>/", views.package_detail, name="package_detail"),
    path("package/<slug:slug>/pdf/", views.package_pdf, name="package_pdf"),
    path("package/<slug:slug>/save/", views.toggle_save, name="toggle_save"),
    path("package/<slug:slug>/enquiry/", views.create_enquiry, name="create_enquiry"),
]
