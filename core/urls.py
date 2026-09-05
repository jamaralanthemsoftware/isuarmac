from django.urls import path

from .views import (
    PageDetailView,
    ServiceDetailView,
    contact,
    healthz,
    home,
    robots_txt,
)

urlpatterns = [
    path("", home, name="home"),
    path("healthz/", healthz, name="healthz"),
    path("robots.txt", robots_txt, name="robots-txt"),
    path("contact/", contact, name="contact"),
    path("services/<slug:slug>/", ServiceDetailView.as_view(), name="service-detail"),
    path("<slug:slug>/", PageDetailView.as_view(), name="page-detail"),
]
