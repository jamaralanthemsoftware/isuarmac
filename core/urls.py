from django.urls import path

from anthem_seo.views import managed_page
from .views import (
    BlogDetailView,
    BlogListView,
    PageDetailView,
    ServiceDetailView,
    about,
    contact,
    faq,
    healthz,
    home,
    robots_txt,
    services,
)

urlpatterns = [
    path("", home, name="home"),
    path("healthz/", healthz, name="healthz"),
    path("robots.txt", robots_txt, name="robots-txt"),
    path("about/", about, name="about"),
    path("contact/", contact, name="contact"),
    path("faq/", faq, name="faq"),
    path("services/", services, name="services"),
    path("services/<slug:slug>/", ServiceDetailView.as_view(), name="service-detail"),
    path("blog/", BlogListView.as_view(), name="blog-list"),
    path("blog/<slug:slug>/", BlogDetailView.as_view(), name="blog-detail"),
    path("<slug:slug>/", PageDetailView.as_view(), name="page-detail"),
    path("<path:seo_path>/", managed_page, name="anthem-managed-page"),
]
