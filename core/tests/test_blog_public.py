from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import BlogPost, BlogPostRelatedSelection, BlogTopic


class PublicBlogTests(TestCase):
    def make_post(self, **overrides):
        number = BlogPost.objects.count()
        values = {
            "title": f"Article {number}",
            "slug": f"article-{number}",
            "summary": "A useful article summary.",
            "body": "<p>Safe imported <strong>HTML</strong>.</p>",
            "author_name": "Editorial Team",
            "original_published_at": timezone.now() - timedelta(days=number),
            "is_published": True,
        }
        values.update(overrides)
        return BlogPost.objects.create(**values)

    def test_listing_and_detail_only_expose_published_posts(self):
        published = self.make_post(title="Published article")
        draft = self.make_post(
            title="Draft article", slug="draft-article", is_published=False
        )

        response = self.client.get(reverse("blog-list"))

        self.assertContains(response, published.title)
        self.assertNotContains(response, draft.title)
        self.assertEqual(self.client.get(published.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)

    def test_listing_is_paginated(self):
        for index in range(11):
            self.make_post(slug=f"post-{index}")

        first_page = self.client.get(reverse("blog-list"))
        second_page = self.client.get(reverse("blog-list"), {"page": 2})

        self.assertEqual(len(first_page.context["posts"]), 10)
        self.assertContains(first_page, "Next")
        self.assertEqual(len(second_page.context["posts"]), 1)
        self.assertContains(second_page, "Previous")

    def test_detail_renders_metadata_byline_date_image_and_safe_imported_html(self):
        post = self.make_post(
            meta_title="Article search title",
            meta_description="Article search description.",
            canonical_url="https://example.com/blog/article/",
            featured_image=SimpleUploadedFile("featured.jpg", b"image-bytes"),
        )

        response = self.client.get(post.get_absolute_url())

        self.assertContains(response, "<title>Article search title</title>", html=True)
        self.assertContains(
            response,
            '<link rel="canonical" href="https://example.com/blog/article/">',
            html=True,
        )
        self.assertContains(response, 'property="og:type" content="article"')
        self.assertContains(response, 'property="og:image" content="http://testserver/')
        self.assertContains(response, "Editorial Team")
        displayed_date = timezone.localtime(post.publication_date).strftime("%B %-d, %Y")
        self.assertContains(response, displayed_date)
        self.assertContains(
            response, '<meta name="twitter:card" content="summary_large_image">'
        )
        self.assertContains(
            response, "<p>Safe imported <strong>HTML</strong>.</p>", html=True
        )

    def test_detail_recommends_three_recent_other_published_articles(self):
        current = self.make_post(
            title="Current article",
            original_published_at=timezone.now() - timedelta(days=10),
        )
        oldest = self.make_post(
            title="Oldest published recommendation",
            original_published_at=timezone.now() - timedelta(days=4),
        )
        recommendations = [
            self.make_post(
                title=f"Recommendation {days}",
                original_published_at=timezone.now() - timedelta(days=days),
            )
            for days in (3, 2, 1)
        ]
        draft = self.make_post(
            title="Recent draft",
            is_published=False,
            original_published_at=timezone.now(),
        )

        # Detail lookup + two shared context processors + editorial and automatic
        # recommendation queries.
        with self.assertNumQueries(5):
            response = self.client.get(current.get_absolute_url())

        related_articles = list(response.context["related_articles"])
        self.assertEqual(related_articles, list(reversed(recommendations)))
        self.assertNotIn(current, related_articles)
        self.assertNotContains(response, oldest.title)
        self.assertNotContains(response, draft.title)
        for recommendation in recommendations:
            self.assertContains(
                response,
                f'href="{recommendation.get_absolute_url()}"',
            )

    def test_detail_prioritizes_ordered_published_editorial_selections(self):
        current = self.make_post(title="Current article")
        automatic = self.make_post(title="Automatic fallback")
        second = self.make_post(
            title="Second editorial choice",
            original_published_at=timezone.now() - timedelta(days=20),
        )
        first = self.make_post(
            title="First editorial choice",
            original_published_at=timezone.now() - timedelta(days=30),
        )
        draft = self.make_post(title="Draft editorial choice", is_published=False)
        BlogPostRelatedSelection.objects.create(
            source_post=current, related_post=second, position=2
        )
        BlogPostRelatedSelection.objects.create(
            source_post=current, related_post=draft, position=3
        )
        BlogPostRelatedSelection.objects.create(
            source_post=current, related_post=first, position=1
        )

        response = self.client.get(current.get_absolute_url())

        self.assertEqual(
            list(response.context["related_articles"]),
            [first, second, automatic],
        )
        self.assertNotContains(response, draft.title)
        content = response.content.decode()
        self.assertLess(content.index(first.title), content.index(second.title))
        self.assertLess(content.index(second.title), content.index(automatic.title))

    def test_detail_does_not_duplicate_an_editorial_selection_in_fallbacks(self):
        current = self.make_post(title="Current article")
        selected = self.make_post(title="Selected recent article")
        fallback_one = self.make_post(title="First fallback")
        fallback_two = self.make_post(title="Second fallback")
        BlogPostRelatedSelection.objects.create(
            source_post=current, related_post=selected, position=1
        )

        response = self.client.get(current.get_absolute_url())

        related_articles = list(response.context["related_articles"])
        self.assertEqual(related_articles, [selected, fallback_one, fallback_two])
        self.assertEqual(related_articles.count(selected), 1)

    def test_sitemap_contains_published_posts_only(self):
        published = self.make_post()
        draft = self.make_post(slug="draft", is_published=False)

        response = self.client.get(reverse("sitemap"))

        self.assertContains(response, published.get_absolute_url())
        self.assertNotContains(response, draft.get_absolute_url())

    def test_detail_prioritizes_shared_topics_then_fills_with_recent_posts(self):
        current = self.make_post(
            title="Current article",
            original_published_at=timezone.now() - timedelta(days=10),
        )
        shared_topic = BlogTopic.objects.create(name="Planning", slug="planning")
        other_topic = BlogTopic.objects.create(name="Growth", slug="growth")
        current.topics.add(shared_topic)

        newest_fallback = self.make_post(
            title="Newest fallback",
            original_published_at=timezone.now(),
        )
        older_match = self.make_post(
            title="Older topic match",
            original_published_at=timezone.now() - timedelta(days=20),
        )
        older_match.topics.add(shared_topic)
        unrelated = self.make_post(
            title="Unrelated article",
            original_published_at=timezone.now() - timedelta(days=2),
        )
        unrelated.topics.add(other_topic)
        draft_match = self.make_post(
            title="Draft topic match",
            is_published=False,
            original_published_at=timezone.now() + timedelta(days=1),
        )
        draft_match.topics.add(shared_topic)

        with self.assertNumQueries(5):
            response = self.client.get(current.get_absolute_url())

        self.assertEqual(
            list(response.context["related_articles"]),
            [older_match, newest_fallback, unrelated],
        )
        self.assertNotContains(response, draft_match.title)

    def test_blogpost_enforces_unique_slug_and_sanitizes_body_on_save(self):
        from django.db import IntegrityError

        post = self.make_post(
            slug="unique-article",
            body='<p>Safe</p><script>alert(1)</script><img src="https://example.com/a.jpg" onerror="alert(1)">',
        )
        self.assertNotIn("<script>", post.body)
        self.assertNotIn("onerror", post.body)
        self.assertIn("<p>Safe</p>", post.body)

        with self.assertRaises(IntegrityError):
            self.make_post(slug="unique-article")
