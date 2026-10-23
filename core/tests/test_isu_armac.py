from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from core import designed_pages
from core.content_fixes import apply_fixes
from core.models import (
    BlogPost,
    BlogTopic,
    LegacyRedirect,
    Lead,
    Page,
    QuoteRequest,
    TeamMember,
)
from core.page_builder import make_placeholders


class IsuArmacConversionTests(TestCase):
    def test_designed_page_builder_renders_home_and_contractor_specs(self):
        TeamMember.objects.create(
            name="Ryan J. Master",
            title="President",
            photo_url="/static/img/team/ryan-j-master.jpg",
            order=0,
            featured=True,
        )
        home_ph = make_placeholders()
        designed_pages.build_home(home_ph)
        home_body = str(home_ph["content"].render())
        self.assertIn("Coverage that fits.", home_body)
        self.assertIn("ISU-ARMAC shops 300+ carriers", home_body)
        self.assertIn("One agency for your home, your business and your people", home_body)

        page = Page.objects.create(
            title="Home",
            slug="home",
            path="/",
            template_name="home.html",
            body=home_body,
            is_published=True,
        )
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ISU-ARMAC shops 300+ carriers")
        self.assertEqual(page.get_absolute_url(), "/")

    def test_nested_page_routing_and_canonical_redirect(self):
        parent = Page.objects.create(
            title="Business Insurance",
            slug="commercial-insurance",
            path="/insurance-center/service/commercial-insurance/",
            template_name="landing.html",
            body="<p>Business insurance hub.</p>",
            is_published=True,
        )
        child = Page.objects.create(
            title="Contractor Insurance",
            slug="contractor-insurance",
            path="/insurance-center/service/commercial-insurance/contractor-insurance/",
            parent=parent,
            template_name="landing.html",
            body="<p>Contractor coverage details across CA, NV, and AZ.</p>",
            is_published=True,
        )
        nested_resp = self.client.get(child.path)
        self.assertEqual(nested_resp.status_code, 200)
        self.assertContains(nested_resp, "Contractor coverage details")
        self.assertContains(nested_resp, "Business Insurance")

        # Visiting bare /contractor-insurance/ redirects 301 to canonical nested path
        short_resp = self.client.get("/contractor-insurance/")
        self.assertEqual(short_resp.status_code, 301)
        self.assertEqual(
            short_resp["Location"],
            "/insurance-center/service/commercial-insurance/contractor-insurance/",
        )

    def test_legacy_uploads_and_service_redirects(self):
        upload_resp = self.client.get("/wp-content/uploads/2024/05/sample.jpg")
        self.assertEqual(upload_resp.status_code, 301)
        self.assertEqual(upload_resp["Location"], "/media/uploads/2024/05/sample.jpg")

        service_resp = self.client.get("/service/business-insurance/")
        self.assertEqual(service_resp.status_code, 301)
        self.assertEqual(
            service_resp["Location"],
            "/insurance-center/service/commercial-insurance/",
        )

        LegacyRedirect.objects.create(
            old_path="/contact-us/",
            new_path="/contact/",
        )
        db_redir = self.client.get("/contact-us/")
        self.assertEqual(db_redir.status_code, 301)
        self.assertEqual(db_redir["Location"], "/contact/")

    @patch("core.views.deliver_lead_to_anthem", return_value=True)
    @patch("core.views.send_contact_lead_notification", return_value=True)
    def test_submit_lead_creates_lead_and_quote_request_for_all_form_types(
        self,
        mock_postmark,
        mock_anthem,
    ):
        payloads = [
            {
                "form_type": "general",
                "name": "Jane Doe",
                "email": "jane@example.com",
                "phone": "760-555-0100",
                "state": "California",
                "quote_type": "Personal (home, auto)",
                "zip_code": "92392",
                "message": "Looking for a homeowners quote.",
                "page_url": "/get-a-quote/",
            },
            {
                "form_type": "contractor",
                "name": "Bob Builder",
                "company": "Builder Co",
                "email": "bob@example.com",
                "phone": "760-555-0101",
                "state": "Nevada",
                "trade": "Electrical",
                "employees": "11 to 50",
                "needs": ["General liability", "Workers' comp"],
            },
            {
                "form_type": "hospital",
                "name": "Dr. Alice Smith",
                "title": "CFO",
                "company": "Desert Valley Hospital",
                "email": "alice@example.com",
                "phone": "760-555-0102",
                "state": "California",
                "beds": "100 to 249",
                "employees": "300 to 999",
                "interests": ["Employee benefits", "Self-insured plan management"],
            },
            {
                "form_type": "benefits",
                "name": "Carlos Ruiz",
                "company": "High Desert Tech",
                "email": "carlos@example.com",
                "phone": "760-555-0103",
                "state": "Arizona",
                "employees": "10 to 49",
                "renewal_month": "October",
            },
            {
                "form_type": "contact",
                "name": "Maria Gomez",
                "email": "maria@example.com",
                "phone": "760-555-0104",
                "message": "Please call me about commercial auto.",
            },
        ]
        for data in payloads:
            resp = self.client.post(reverse("submit_lead"), data)
            self.assertEqual(resp.status_code, 302)
            self.assertEqual(resp["Location"], "/thank-you/")

        self.assertEqual(Lead.objects.count(), 5)
        self.assertEqual(QuoteRequest.objects.count(), 5)
        contractor_qr = QuoteRequest.objects.get(form_type="contractor")
        self.assertEqual(contractor_qr.details["trade"], "Electrical")
        self.assertIsNotNone(contractor_qr.lead)
        self.assertEqual(mock_anthem.call_count, 5)
        self.assertEqual(mock_postmark.call_count, 5)

    def test_submit_lead_honeypot_and_invalid_submission(self):
        honeypot_resp = self.client.post(
            reverse("submit_lead"),
            {
                "form_type": "general",
                "name": "Spam Bot",
                "email": "bot@example.com",
                "phone": "760-555-0199",
                "quote_type": "Business",
                "website": "https://spam.example.com",
            },
        )
        self.assertEqual(honeypot_resp.status_code, 302)
        self.assertEqual(Lead.objects.count(), 0)
        self.assertEqual(QuoteRequest.objects.count(), 0)

        invalid_resp = self.client.post(
            reverse("submit_lead"),
            {"form_type": "general", "name": "", "email": "not-an-email"},
        )
        self.assertEqual(invalid_resp.status_code, 400)

    def test_blog_category_view_and_html_sitemap(self):
        topic = BlogTopic.objects.create(name="Business Insurance", slug="business-insurance")
        post = BlogPost.objects.create(
            title="Understanding Commercial Auto Coverage",
            slug="understanding-commercial-auto-coverage",
            summary="A guide to commercial auto policies.",
            body="<p>Full article body.</p>",
            is_published=True,
        )
        post.topics.add(topic)

        cat_resp = self.client.get(
            reverse("blog_category", kwargs={"category": "business-insurance"})
        )
        self.assertEqual(cat_resp.status_code, 200)
        self.assertContains(cat_resp, "Understanding Commercial Auto Coverage")

        Page.objects.create(
            title="Industries",
            slug="industries",
            path="/industries/",
            body="<p>Industries we insure.</p>",
            is_published=True,
        )
        sitemap_resp = self.client.get(reverse("html_site_map"))
        self.assertEqual(sitemap_resp.status_code, 200)
        self.assertContains(sitemap_resp, "Industries")

    def test_content_fixes_normalizes_brand_name(self):
        fixed = apply_fixes("Contact ISU Armac for a quote today.")
        self.assertIn("ISU-ARMAC", fixed)
