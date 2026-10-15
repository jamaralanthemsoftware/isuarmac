import tempfile
from io import BytesIO
import socket
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.blog_importer import (
    MAX_ITEMS,
    MAX_RESPONSE_BYTES,
    ImportErrorMessage,
    run_import,
    sitemap_urls,
    validate_source_url,
    _verified_image_extension,
)
from core.models import BlogImportItem, BlogImportRun, BlogPost


class FakeResponse:
    def __init__(self, body=b"", content_type="application/xml", status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = {"Content-Type": content_type, **(headers or {})}
        self._read = False

    def read(self, size=-1):
        if self._read:
            return b""
        self._read = True
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def close(self):
        return None


class FakeOpener:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []


WXR = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:wp="http://wordpress.org/export/1.2/"><channel>
<item><title>Imported &amp; useful</title><link>https://source.example/blog/one/</link>
<guid isPermaLink="false">post-123</guid><dc:creator>Writer Name</dc:creator>
<pubDate>Tue, 01 Oct 2024 12:00:00 +0000</pubDate>
<content:encoded><![CDATA[<p>Hello <strong>world</strong>.</p>]]></content:encoded>
<excerpt:encoded xmlns:excerpt="http://wordpress.org/export/1.2/"><![CDATA[An excerpt.]]></excerpt:encoded>
<wp:post_id>123</wp:post_id><wp:post_name>one</wp:post_name>
<wp:post_type>post</wp:post_type><wp:post_date_gmt>2024-10-01 12:00:00</wp:post_date_gmt>
<wp:post_modified_gmt>2024-10-02 12:00:00</wp:post_modified_gmt></item>
</channel></rss>"""


def sitemap_index():
    return b"""<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://source.example/wp-sitemap-posts-post-1.xml</loc></sitemap>
    </sitemapindex>"""


def sitemap_urlset():
    return b"""<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://source.example/blog/crawled/</loc></url></urlset>"""


PAGE = b"""<html><head><title>Page title</title>
<meta name="description" content="A page description">
<meta property="og:image" content="/media/hero.png">
<link rel="canonical" href="https://source.example/blog/crawled/"></head>
<body><article><h2>Heading</h2><p>Safe <strong>content</strong>.</p>
<script>alert('remove me')</script><img src="/media/hero.png" alt="Hero"></article></body></html>"""


def valid_png():
    output = BytesIO()
    Image.new("RGB", (2, 2), "red").save(output, format="PNG")
    return output.getvalue()


class BlogImporterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="importer", email="importer@example.com", password="secure-password"
        )

    def network(self, responses):
        opener = FakeOpener(responses)

        def open_response(parsed, _addresses, _timeout, _headers):
            url = parsed.geturl()
            opener.requests.append((url, _timeout))
            response = responses[url]
            return FakeConnection(), response

        return patch.multiple(
            "core.blog_importer",
            _open_validated_response=Mock(side_effect=open_response),
            _public_ip=Mock(return_value={"203.0.113.10"}),
        ), opener

    def test_wxr_creates_draft_with_namespaces_and_dates(self):
        run = run_import(user=self.user, mode="wxr", payload=WXR, uploaded_name="export.xml")

        post = BlogPost.objects.get(source_guid="post-123")
        self.assertEqual(run.status, BlogImportRun.Status.COMPLETED)
        self.assertEqual(run.imported_count, 1)
        self.assertFalse(post.is_published)
        self.assertEqual(post.title, "Imported & useful")
        self.assertEqual(post.slug, "one")
        self.assertEqual(post.author_name, "Writer Name")
        self.assertEqual(post.source_url, "https://source.example/blog/one/")
        self.assertIn("<strong>world</strong>", post.body)
        self.assertIsNotNone(post.original_published_at)
        self.assertIsNotNone(post.original_modified_at)

    def test_wxr_attachment_relationship_is_available_to_image_downloader(self):
        wxr = WXR.replace(
            b"</channel>",
            b"""<item><title>Hero</title><wp:post_id>500</wp:post_id>
            <wp:post_type>attachment</wp:post_type>
            <wp:attachment_url>https://source.example/uploads/hero.jpg</wp:attachment_url>
            </item><item><title>With image</title><link>https://source.example/with-image/</link>
            <guid>with-image-guid</guid><wp:post_id>501</wp:post_id><wp:post_name>with-image</wp:post_name>
            <wp:post_type>post</wp:post_type><wp:postmeta><wp:meta_key>_thumbnail_id</wp:meta_key>
            <wp:meta_value>500</wp:meta_value></wp:postmeta></item></channel>""",
        )
        with patch("core.blog_importer._save_image", return_value=1) as save:
            run_import(user=self.user, mode="wxr", payload=wxr)

        save.assert_called_once()
        self.assertEqual(BlogPost.objects.filter(is_published=False).count(), 2)

    def test_sitemap_index_and_urlset_crawl_same_origin(self):
        responses = {
            "https://source.example/sitemap.xml": FakeResponse(sitemap_index()),
            "https://source.example/wp-sitemap-posts-post-1.xml": FakeResponse(sitemap_urlset()),
            "https://source.example/blog/crawled/": FakeResponse(PAGE, "text/html"),
            "https://source.example/media/hero.png": FakeResponse(b"not-an-image", "image/svg+xml"),
        }
        context, opener = self.network(responses)
        with context:
            run = run_import(user=self.user, mode="sitemap", source_url="https://source.example/sitemap.xml")

        post = BlogPost.objects.get(source_url="https://source.example/blog/crawled/")
        self.assertEqual(run.imported_count, 1)
        self.assertEqual(post.meta_description, "A page description")
        self.assertEqual(post.canonical_url, "https://source.example/blog/crawled/")
        self.assertNotIn("alert", post.body)
        self.assertTrue(any("/blog/crawled/" in url for url, _timeout in opener.requests))

    def test_duplicate_guid_or_source_url_is_skipped_and_reported(self):
        first = run_import(user=self.user, mode="wxr", payload=WXR)
        second = run_import(user=self.user, mode="wxr", payload=WXR)

        self.assertEqual(first.imported_count, 1)
        self.assertEqual(second.duplicate_count, 1)
        self.assertEqual(BlogPost.objects.count(), 1)
        item = BlogImportItem.objects.get(run=second)
        self.assertEqual(item.status, BlogImportItem.Status.DUPLICATE)
        self.assertEqual(item.blog_post, BlogPost.objects.get())

    def test_featured_image_priority_and_failure_keep_draft(self):
        responses = {
            "https://source.example/sitemap.xml": FakeResponse(sitemap_urlset()),
            "https://source.example/blog/crawled/": FakeResponse(PAGE, "text/html"),
            "https://source.example/media/hero.png": FakeResponse(
                b"not-an-image", "image/svg+xml"
            ),
        }
        context, _opener = self.network(responses)
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()), context:
            run = run_import(user=self.user, mode="sitemap", source_url="https://source.example/sitemap.xml")

        post = BlogPost.objects.get()
        item = BlogImportItem.objects.get(run=run)
        self.assertFalse(post.is_published)
        self.assertEqual(run.imported_count, 1)
        self.assertFalse(post.featured_image)
        self.assertIn("featured_image_error", item.details)

    def test_featured_png_is_saved_when_allowed(self):
        responses = {
            "https://source.example/sitemap.xml": FakeResponse(sitemap_urlset()),
            "https://source.example/blog/crawled/": FakeResponse(PAGE, "text/html"),
            "https://source.example/media/hero.png": FakeResponse(
                valid_png(), "image/png"
            ),
        }
        context, _opener = self.network(responses)
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()), context:
            run = run_import(user=self.user, mode="sitemap", source_url="https://source.example/sitemap.xml")

        self.assertEqual(run.imported_count, 1)
        self.assertTrue(BlogPost.objects.get().featured_image.name.endswith(".png"))

    def test_fake_content_type_and_riff_payloads_are_rejected(self):
        with self.assertRaises(ImportErrorMessage):
            _verified_image_extension("image/jpeg", valid_png())
        with self.assertRaises(ImportErrorMessage):
            _verified_image_extension("image/webp", b"RIFF\x00\x00\x00\x00WEBP")

    def test_shared_budget_counts_page_and_invalid_image_bytes(self):
        responses = {
            "https://source.example/sitemap.xml": FakeResponse(sitemap_urlset()),
            "https://source.example/blog/crawled/": FakeResponse(PAGE, "text/html"),
            "https://source.example/media/hero.png": FakeResponse(
                b"x" * 100, "image/svg+xml"
            ),
        }
        context, opener = self.network(responses)
        budget = len(sitemap_urlset()) + len(PAGE) + 20
        with patch("core.blog_importer.MAX_TOTAL_BYTES", budget), context:
            run = run_import(user=self.user, mode="sitemap", source_url="https://source.example/sitemap.xml")

        self.assertEqual(run.status, BlogImportRun.Status.FAILED)
        self.assertIn("exhausted", run.error_summary)
        self.assertEqual(run.imported_count, 1)
        self.assertEqual(BlogPost.objects.count(), 1)
        self.assertTrue(any("media/hero.png" in url for url, _timeout in opener.requests))

    def test_dtd_and_entity_xml_are_rejected(self):
        malicious = b'<!DOCTYPE rss [<!ENTITY xxe "bad">]><rss><channel/></rss>'
        run = run_import(user=self.user, mode="wxr", payload=malicious)

        self.assertEqual(run.status, BlogImportRun.Status.FAILED)
        self.assertIn("DTD", run.error_summary)
        self.assertEqual(BlogPost.objects.count(), 0)

    def test_upload_response_and_item_limits_are_enforced(self):
        oversized = b"x" * (10 * 1024 * 1024 + 1)
        run = run_import(user=self.user, mode="wxr", payload=oversized)
        self.assertEqual(run.status, BlogImportRun.Status.FAILED)

        responses = {"https://source.example/sitemap.xml": FakeResponse(b"x" * (MAX_RESPONSE_BYTES + 1))}
        context, _opener = self.network(responses)
        with context:
            response_run = run_import(
                user=self.user, mode="sitemap", source_url="https://source.example/sitemap.xml"
            )
        self.assertEqual(response_run.status, BlogImportRun.Status.FAILED)
        self.assertEqual(MAX_ITEMS, 500)

    def test_sitemap_item_limit_stops_at_configured_maximum(self):
        entries = "".join(
            f"<url><loc>https://source.example/post-{index}/</loc></url>"
            for index in range(MAX_ITEMS + 1)
        )
        sitemap = f"<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>{entries}</urlset>".encode()
        responses = {"https://source.example/sitemap.xml": FakeResponse(sitemap)}
        context, _opener = self.network(responses)
        with context:
            urls, _origin, _used = sitemap_urls(
                "https://source.example/sitemap.xml", 50 * 1024 * 1024
            )
        self.assertEqual(len(urls), MAX_ITEMS)

    def test_private_reserved_and_unsafe_redirect_urls_are_rejected(self):
        for url in ["http://127.0.0.1/sitemap.xml", "http://169.254.169.254/metadata"]:
            with self.subTest(url=url), self.assertRaises(ImportErrorMessage):
                validate_source_url(url)

        responses = {
            "https://source.example/sitemap.xml": FakeResponse(
                status=302, headers={"Location": "http://127.0.0.1/private"}
            )
        }
        context, _opener = self.network(responses)
        from core.blog_importer import fetch_url

        def reject_private(hostname):
            if hostname == "127.0.0.1":
                raise ImportErrorMessage("private address")

        with context, patch("core.blog_importer._public_ip", side_effect=reject_private):
            with self.assertRaises(ImportErrorMessage):
                fetch_url("https://source.example/sitemap.xml")

    def test_dns_revalidation_cannot_change_to_private_destination(self):
        public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]
        private = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
        with patch("core.blog_importer.socket.getaddrinfo", side_effect=[public, private]):
            with self.assertRaises(ImportErrorMessage):
                from core.blog_importer import fetch_url
                fetch_url("https://source.example/sitemap.xml")

    def test_sitemap_cross_origin_url_is_rejected(self):
        responses = {
            "https://source.example/sitemap.xml": FakeResponse(
                b"""<urlset><url><loc>https://other.example/post/</loc></url></urlset>"""
            )
        }
        context, _opener = self.network(responses)
        with context:
            run = run_import(user=self.user, mode="sitemap", source_url="https://source.example/sitemap.xml")
        self.assertEqual(run.status, BlogImportRun.Status.FAILED)
        self.assertIn("original site origin", run.error_summary)

    def test_persistent_run_and_item_reports_are_created(self):
        run = run_import(user=self.user, mode="wxr", payload=WXR)

        self.assertEqual(run.items.count(), 1)
        self.assertEqual(run.items.first().blog_post.title, "Imported & useful")
        self.assertTrue(run.finished_at)

    def test_wxr_excerpt_strips_html_tags_and_safe_html_fallback_strips_attributes(self):
        from core.blog_importer import _safe_html

        wxr_with_html_excerpt = WXR.replace(
            b"An excerpt.",
            b"<p>An <strong>important</strong> &amp; clean excerpt.</p>",
        )
        run_import(user=self.user, mode="wxr", payload=wxr_with_html_excerpt)
        post = BlogPost.objects.get(source_guid="post-123")
        self.assertEqual(post.summary, "An important & clean excerpt.")
        self.assertEqual(post.meta_description, "An important & clean excerpt.")

        with patch("core.blog_importer.bleach", None):
            cleaned = _safe_html('<p onclick="alert(1)">Hello</p><img src="x" onerror="alert(1)">')
        self.assertEqual(cleaned, "<p>Hello</p>")


class BlogImporterAdminAccessTests(TestCase):
    def setUp(self):
        self.url = reverse("admin:blog-import")
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="staff", password="secure-password", is_staff=True
        )
        self.superuser = user_model.objects.create_superuser(
            username="root", email="root@example.com", password="secure-password"
        )

    def test_anonymous_and_staff_users_cannot_open_importer(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_superuser_can_open_and_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.superuser)
        self.assertEqual(client.get(self.url).status_code, 200)
        response = client.post(
            self.url,
            {"mode": "wxr", "wxr_file": SimpleUploadedFile("empty.xml", b"<rss/>")},
        )
        self.assertEqual(response.status_code, 403)

    @patch("core.admin.run_import")
    def test_superuser_post_uses_importer_and_shows_report(self, run_import_mock):
        run = BlogImportRun.objects.create(
            mode=BlogImportRun.Mode.WXR, status=BlogImportRun.Status.COMPLETED,
            imported_count=1, created_by=self.superuser,
        )
        run_import_mock.return_value = run
        self.client.force_login(self.superuser)
        response = self.client.post(
            self.url,
            {"mode": "wxr", "wxr_file": SimpleUploadedFile("export.xml", WXR)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import complete")
        run_import_mock.assert_called_once()

    def test_import_item_direct_view_change_and_delete_are_superuser_only(self):
        run = BlogImportRun.objects.create(
            mode=BlogImportRun.Mode.WXR, status=BlogImportRun.Status.COMPLETED,
            created_by=self.superuser,
        )
        item = BlogImportItem.objects.create(
            run=run, status=BlogImportItem.Status.FAILED, error_summary="review"
        )
        change_url = reverse("admin:core_blogimportitem_change", args=[item.pk])
        delete_url = reverse("admin:core_blogimportitem_delete", args=[item.pk])

        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(change_url).status_code, 403)
        self.assertEqual(self.client.get(delete_url).status_code, 403)

        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(change_url).status_code, 200)
        self.assertEqual(self.client.get(delete_url).status_code, 200)