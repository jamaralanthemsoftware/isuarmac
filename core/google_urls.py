from django.urls import path

from .google_views import callback, connect, dashboard, disconnect


urlpatterns = [
    path("", dashboard, name="google-services-dashboard"),
    path("connect/", connect, name="google-services-connect"),
    path("callback/", callback, name="google-services-callback"),
    path("disconnect/", disconnect, name="google-services-disconnect"),
]