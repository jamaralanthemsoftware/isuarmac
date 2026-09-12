import io
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage, default_storage
from django.http import HttpResponse
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import path, reverse
from PIL import Image

from core.image_pipeline import image_dimensions, responsive_renditions
from core.middleware import PublicPageCacheMiddleware
from core.models import SiteSettings


def message_view(request):
    messages.success(request, "A test message")
    return HttpResponse("message")


urlpatterns = [path("test-message/", message_view)]


def image_upload(name="hero.png", size=(900, 450), image_format="PNG"):
    output = io.BytesIO()
    Image.new("RGB", size, (25, 100, 80)).save(output, format=image_format)
    return output.getvalue()


class ResponsiveImagePipelineTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = self.enterContext(tempfile.TemporaryDirectory())
        self.storage = default_storage._wrapped
        default_storage._wrapped = FileSystemStorage(location=self.temp_dir)

    def tearDown(self):
        default_storage._wrapped = self.storage

    def test_renditions_are_webp_bounded_and_reused(self):
        from django.core.files.base import ContentFile

        source = ContentFile(image_upload(size=(2400, 1200)), name="hero.png")
        first = responsive_renditions(source, widths=(320, 640, 2400, 5000))
        second = responsive_renditions(source, widths=(320, 640, 2400, 5000))

        self.assertEqual([item.width for item in first], [320, 640, 2000])
        self.assertEqual([item.url for item in first], [item.url for item in second])
        self.assertTrue(all(item.url.endswith(".webp") for item in first))
        self.assertTrue(all(item.width <= 2000 for item in first))

    def test_same_name_replacement_gets_a_new_rendition_url(self):
        from django.core.files.base import ContentFile

        original = ContentFile(image_upload(size=(900, 450)), name="hero.png")
        replacement = ContentFile(
            image_upload(size=(900, 600), image_format="JPEG"),
            name="hero.png",
        )

        original_url = responsive_renditions(original, widths=(320, 900))[-1].url
        replacement_url = responsive_renditions(replacement, widths=(320, 900))[-1].url

        self.assertNotEqual(original_url, replacement_url)

    def test_intrinsic_dimensions_are_numeric_source_dimensions(self):
        from django.core.files.base import ContentFile

        width, height = image_dimensions(
            ContentFile(image_upload(size=(777, 333)), name="intrinsic.png")
        )

        self.assertIsInstance(width, int)
        self.assertIsInstance(height, int)
        self.assertEqual((width, height), (777, 333))

    def test_malformed_oversized_and_decompression_bomb_images_are_rejected(self):
        from django.core.files.base import ContentFile

        malformed = ContentFile(b"not an image", name="bad.png")
        with self.assertRaises(ValueError):
            responsive_renditions(malformed)

        with patch("core.image_pipeline.MAX_SOURCE_PIXELS", 10):
            with self.assertRaises(ValueError):
                responsive_renditions(
                    ContentFile(image_upload(size=(4, 4)), name="too-large.png")
                )

        with patch(
            "core.image_pipeline.Image.open",
            side_effect=Image.DecompressionBombError("bomb"),
        ):
            with self.assertRaises(ValueError):
                responsive_renditions(
                    ContentFile(image_upload(size=(20, 20)), name="bomb.png")
                )


class ResponsiveImageTemplateTests(TestCase):
    def render(self, image, **kwargs):
        arguments = " ".join(
            f'{key}="{value}"' if isinstance(value, str) else f"{key}={value}"
            for key, value in kwargs.items()
        )
        template = Template(
            "{% load performance_tags %}"
            f'{{% responsive_image image "A hero" {arguments} %}}'
        )
        return template.render(Context({"image": image}))

    def test_lcp_image_is_eager_and_high_priority(self):
        from django.core.files.base import ContentFile

        html = self.render(ContentFile(image_upload(), name="hero.png"), lcp=True)

        self.assertIn('width="900"', html)
        self.assertIn('height="450"', html)
        self.assertIn('loading="eager"', html)
        self.assertIn('fetchpriority="high"', html)
        self.assertIn("srcset=", html)
        self.assertIn("sizes=", html)
        self.assertIn(" 900w", html)
        self.assertEqual(html.count(" 900w"), 1)

    def test_below_fold_image_is_lazy_and_not_high_priority(self):
        from django.core.files.base import ContentFile

        html = self.render(ContentFile(image_upload(), name="below.png"))

        self.assertIn('loading="lazy"', html)
        self.assertIn('fetchpriority="auto"', html)
        self.assertNotIn('fetchpriority="high"', html)


class AnalyticsAndThirdPartyTemplateTests(TestCase):
    def test_analytics_is_absent_without_measurement_id(self):
        response = self.client.get(reverse("home"))

        self.assertNotContains(response, "googletagmanager.com/gtag/js")
        self.assertNotContains(response, "__ga4Loaded")

    @override_settings(ANALYTICS_CONSENT_REQUIRED=True)
    def test_analytics_waits_for_consent_when_required(self):
        SiteSettings.objects.create(analytics_measurement_id="G-TEST123")

        response = self.client.get(reverse("home"))
        content = response.content.decode()

        self.assertContains(response, "consentRequired = true")
        self.assertContains(response, "analytics-consent-granted")
        self.assertContains(response, "requestIdleCallback")
        self.assertEqual(
            content.count('window.addEventListener("analytics-consent-granted"'),
            1,
        )
        self.assertLess(
            content.index('window.addEventListener("analytics-consent-granted"'),
            content.index("if (!measurementId) return;"),
        )

    @override_settings(ANALYTICS_CONSENT_REQUIRED=False)
    def test_analytics_loads_immediately_when_consent_not_required(self):
        SiteSettings.objects.create(analytics_measurement_id="G-TEST123")

        response = self.client.get(reverse("home"))
        content = response.content.decode()

        self.assertIn("consentRequired = false", content)
        self.assertIn("if (!consentRequired) {\n      load();", content)
        self.assertEqual(content.count("googletagmanager.com/gtag/js"), 1)
        self.assertIn("if (window.__ga4Loaded) return;", content)
        self.assertIn("window.__ga4Loaded = true;", content)

    @override_settings(THIRD_PARTY_SCRIPT_ORIGINS={"https://example.test"})
    def test_selective_third_party_helper_is_deferred_and_marked(self):
        html = Template(
            '{% load performance_tags %}'
            '{% third_party_script "https://example.test/maps.js" "maps" %}'
        ).render(Context())

        self.assertIn('src="https://example.test/maps.js"', html)
        self.assertIn('data-third-party="maps"', html)
        self.assertIn(" defer", html)

    @override_settings(THIRD_PARTY_SCRIPT_ORIGINS={"https://example.test"})
    def test_third_party_helper_rejects_unsafe_and_unapproved_urls(self):
        template = Template(
            '{% load performance_tags %}'
            '{% third_party_script src "maps" %}'
        )
        for src in (
            "http://example.test/maps.js",
            "javascript:alert(1)",
            "data:text/javascript,alert(1)",
            "https://user:password@example.test/maps.js",
            "https://other.example.test/maps.js",
        ):
            with self.subTest(src=src), self.assertRaises(ValueError):
                template.render(Context({"src": src}))


class PublicPageCacheMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = PublicPageCacheMiddleware(
            lambda request: HttpResponse("ok")
        )

    def request(self, path="/", method="get", **attributes):
        cookie = attributes.pop("HTTP_COOKIE", None)
        request = getattr(self.factory, method.lower())(path)
        if cookie:
            request.META["HTTP_COOKIE"] = cookie
            request.COOKIES = {part.split("=", 1)[0].strip(): part.split("=", 1)[1]
                               for part in cookie.split(";") if "=" in part}
        for name, value in attributes.items():
            setattr(request, name, value)
        return request

    def assert_public_cache(self, request, response=None):
        response = response or HttpResponse("ok")
        result = PublicPageCacheMiddleware(lambda request: response)(request)
        self.assertEqual(
            result["Cache-Control"],
            "public, max-age=60, s-maxage=300, stale-while-revalidate=86400",
        )

    def assert_not_public_cache(self, request, response=None):
        response = response or HttpResponse("ok")
        result = PublicPageCacheMiddleware(lambda request: response)(request)
        self.assertNotIn("Cache-Control", result)

    def test_only_anonymous_cookie_free_successful_get_and_head_are_cached(self):
        self.assert_public_cache(self.request())
        self.assert_public_cache(self.request(method="head"))
        self.assert_not_public_cache(self.request(method="post"))
        self.assert_not_public_cache(
            self.request(), HttpResponse("error", status=500)
        )

    @override_settings(ADMIN_URL="secure-admin/")
    def test_admin_and_authenticated_requests_are_not_cached(self):
        self.assert_not_public_cache(self.request("/secure-admin/"))
        self.assert_not_public_cache(self.request("/secure-admin/login/"))
        self.assert_not_public_cache(
            self.request(user=SimpleNamespace(is_authenticated=True))
        )

    def test_cookie_session_message_and_set_cookie_responses_are_not_cached(self):
        self.assert_not_public_cache(
            self.request(HTTP_COOKIE="visitor=1")
        )
        self.assert_not_public_cache(
            self.request(
                HTTP_COOKIE="sessionid=existing",
                session=SimpleNamespace(accessed=True, modified=False),
            )
        )
        message_request = self.request(
            session=SimpleNamespace(accessed=True, modified=True)
        )
        self.assert_not_public_cache(message_request)

        response = HttpResponse("ok")
        response.set_cookie("sessionid", "new")
        self.assert_not_public_cache(self.request(), response)

    def test_vary_cookie_and_existing_private_directives_are_not_overridden(self):
        vary_cookie = HttpResponse("ok", headers={"Vary": "Cookie"})
        self.assert_not_public_cache(self.request(), vary_cookie)
        private = HttpResponse("ok", headers={"Cache-Control": "private"})
        result = PublicPageCacheMiddleware(lambda request: private)(self.request())
        self.assertEqual(result["Cache-Control"], "private")


class PublicPageCacheIntegrationTests(TestCase):
    def assert_not_public(self, response):
        self.assertNotEqual(
            response.get("Cache-Control"),
            "public, max-age=60, s-maxage=300, stale-while-revalidate=86400",
        )

    def test_anonymous_public_page_is_cacheable(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(
            response["Cache-Control"],
            "public, max-age=60, s-maxage=300, stale-while-revalidate=86400",
        )

    def test_csrf_and_session_responses_are_not_cacheable(self):
        csrf_response = self.client.get(reverse("contact"))
        self.assertIn("csrftoken", csrf_response.cookies)
        self.assert_not_public(csrf_response)

        session = self.client.session
        session["personalized"] = "yes"
        session.save()
        session_response = self.client.get(reverse("home"))
        self.assert_not_public(session_response)

    @override_settings(ROOT_URLCONF=__name__)
    def test_message_response_is_not_cacheable(self):
        response = self.client.get("/test-message/")

        self.assertIn("messages", response.cookies)
        self.assert_not_public(response)

    def test_auth_account_admin_and_emergency_login_are_not_cacheable(self):
        user = get_user_model().objects.create_user(
            username="cache-user",
            email="cache-user@example.com",
            password="a-long-development-password",
        )
        self.client.force_login(user)
        self.assert_not_public(self.client.get(reverse("home")))
        self.client.logout()

        self.assert_not_public(self.client.get(reverse("account_login")))
        self.assert_not_public(self.client.get(reverse("admin:login")))
        self.assert_not_public(self.client.get(reverse("emergency-admin-login")))

    def test_admin_restrictive_directives_are_preserved(self):
        response = self.client.get(reverse("admin:login"))

        self.assertIn("no-cache", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
