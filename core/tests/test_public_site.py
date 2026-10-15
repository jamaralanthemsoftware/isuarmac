from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import DownloadableAsset, FAQ, Page, Service, SiteSettings


class PublicSiteStructureTests(TestCase):
    def test_required_pages_render_without_content_records(self):
        for name in ["home", "about", "services", "faq", "contact"]:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)

    def test_header_and_footer_include_required_navigation(self):
        response = self.client.get(reverse("home"))

        for label in ["Home", "About us", "Services", "FAQ", "Contact us"]:
            with self.subTest(label=label):
                self.assertContains(response, label)

    def test_about_page_uses_published_about_record(self):
        Page.objects.create(
            title="Our story",
            slug="about",
            body="Client-managed about content.",
            is_published=True,
        )

        response = self.client.get(reverse("about"))

        self.assertContains(response, "Our story")
        self.assertContains(response, "Client-managed about content.")

    def test_service_listing_links_to_each_published_service(self):
        service = Service.objects.create(
            title="Example service",
            slug="example-service",
            summary="A useful service.",
            is_published=True,
        )

        response = self.client.get(reverse("services"))

        self.assertContains(response, service.title)
        self.assertContains(response, service.get_absolute_url())
        self.assertEqual(self.client.get(service.get_absolute_url()).status_code, 200)

    def test_faq_page_shows_only_published_items(self):
        FAQ.objects.create(
            question="Published question?",
            answer="Published answer.",
            is_published=True,
        )
        FAQ.objects.create(
            question="Draft question?",
            answer="Draft answer.",
            is_published=False,
        )

        response = self.client.get(reverse("faq"))

        self.assertContains(response, "Published question?")
        self.assertNotContains(response, "Draft question?")

    def test_page_generates_search_and_open_graph_metadata_from_content(self):
        page = Page.objects.create(
            title="Planning for a confident retirement",
            slug="retirement-planning",
            summary="Understand the steps involved in building a durable financial plan.",
            body="Detailed planning guidance.",
            is_published=False,
        )

        self.assertEqual(page.meta_title, page.title)
        self.assertEqual(page.open_graph_title, page.title)
        self.assertIn("durable financial plan", page.meta_description)
        self.assertIn("durable financial plan", page.open_graph_description)

    def test_published_content_page_warns_outside_recommended_word_count(self):
        page = Page(
            title="Short page",
            slug="short-page",
            body="Too short.",
            is_published=True,
        )

        page.full_clean()
        self.assertIn("650–900", page.word_count_warning)

        page.body = " ".join(["useful"] * 750)
        page.full_clean()
        self.assertEqual(page.word_count_warning, "")

    def test_downloadable_asset_serves_only_when_published(self):
        published_asset = DownloadableAsset.objects.create(
            title="Client Guide",
            slug="client-guide",
            file=SimpleUploadedFile("guide.pdf", b"%PDF-1.4 guide"),
            is_published=True,
        )
        draft_asset = DownloadableAsset.objects.create(
            title="Draft Guide",
            slug="draft-guide",
            file=SimpleUploadedFile("draft.pdf", b"%PDF-1.4 draft"),
            is_published=False,
        )

        response = self.client.get(published_asset.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        response.close()

        self.assertEqual(self.client.get(draft_asset.get_absolute_url()).status_code, 404)

    def test_site_settings_validates_ga4_measurement_id(self):
        invalid_settings = SiteSettings(analytics_measurement_id="UA-12345-1")
        with self.assertRaises(ValidationError):
            invalid_settings.full_clean()

        valid_settings = SiteSettings(analytics_measurement_id="G-ABC123XYZ")
        valid_settings.full_clean()

    def test_detail_page_assigns_article_open_graph_elements(self):
        page = Page.objects.create(
            title="Detailed guidance",
            slug="detailed-guidance",
            summary="A focused description for search and sharing.",
            body=" ".join(["guidance"] * 750),
            open_graph_image=SimpleUploadedFile("sharing.jpg", b"image-bytes"),
            is_published=True,
        )

        response = self.client.get(page.get_absolute_url())

        self.assertContains(response, 'property="og:type" content="article"')
        self.assertContains(response, f'property="og:title" content="{page.open_graph_title}"')
        self.assertContains(response, 'property="og:image" content="http://testserver/')

    def test_robots_txt_and_static_sitemap_and_reserved_page_slugs(self):
        robots_response = self.client.get(reverse("robots-txt"))
        self.assertEqual(robots_response.status_code, 200)
        self.assertContains(robots_response, "Sitemap: http://testserver/sitemap.xml")

        sitemap_response = self.client.get(reverse("sitemap"))
        self.assertEqual(sitemap_response.status_code, 200)
        for route_name in ("home", "about", "services", "blog-list", "faq", "contact"):
            self.assertContains(sitemap_response, reverse(route_name))

        reserved_page = Page(
            title="Reserved",
            slug="services",
            body="Reserved route test.",
            is_published=False,
        )
        with self.assertRaises(ValidationError):
            reserved_page.full_clean()