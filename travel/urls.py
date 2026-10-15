from django.urls import path

from . import views, integration_views

urlpatterns = [
    path("sitemap.xml", integration_views.sitemap, name="sitemap"),
    path("robots.txt", integration_views.robots, name="robots"),
    path("contact/", integration_views.contact, name="contact"),
    path("contact/thanks/", integration_views.contact, name="contact_thanks"),
    path("api/journeys/", integration_views.journey_search, name="journey_search"),
    path("api/crm/v1/<str:resource>/", integration_views.crm_export, name="crm_export"),
    path("staff/quotation/<str:reference>/pdf/", integration_views.quotation_pdf, name="quotation_pdf"),
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
