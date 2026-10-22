from cms.sitemaps import CMSSitemap
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from site_core import views
from site_core.models import BlogPost


class BlogSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return BlogPost.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.published


urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": {"pages": CMSSitemap, "blog": BlogSitemap}},
         name="django.contrib.sitemaps.views.sitemap"),
    path("lead/", views.submit_lead, name="submit_lead"),
    path("blog/", views.blog_index, name="blog_index"),
    path("blog/category/<slug:category>/", views.blog_index, name="blog_category"),
    path("site-map/", views.html_site_map, name="html_site_map"),
    path("<slug:slug>/", views.post_or_page, name="post_or_page"),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [path("", include("cms.urls"))]
