from django.urls import path

from .views import (
    BlogDetailView,
    BlogListView,
    PageDetailView,
    ServiceDetailView,
    about,
    contact,
    download_asset,
    faq,
    healthz,
    home,
    html_site_map,
    nested_or_managed_page,
    robots_txt,
    services,
    submit_lead,
)

urlpatterns = [
    path("", home, name="home"),
    path("healthz/", healthz, name="healthz"),
    path("robots.txt", robots_txt, name="robots-txt"),
    path("lead/", submit_lead, name="submit_lead"),
    path("site-map/", html_site_map, name="html_site_map"),
    path("about/", about, name="about"),
    path("contact/", contact, name="contact"),
    path("faq/", faq, name="faq"),
    path("services/", services, name="services"),
    path("services/<slug:slug>/", ServiceDetailView.as_view(), name="service-detail"),
    path("downloads/<slug:slug>/", download_asset, name="download-asset"),
    path("blog/", BlogListView.as_view(), name="blog-list"),
    path("blog/category/<slug:category>/", BlogListView.as_view(), name="blog_category"),
    path("blog/<slug:slug>/", BlogDetailView.as_view(), name="blog-detail"),
    path("<slug:slug>/", PageDetailView.as_view(), name="page-detail"),
    path("<path:seo_path>/", nested_or_managed_page, name="anthem-managed-page"),
]
