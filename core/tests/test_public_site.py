from django.test import TestCase
from django.urls import reverse

from core.models import FAQ, Page, Service


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