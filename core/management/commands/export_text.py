"""Export the visible text of every page and post to import_cache/proof/ for proofreading."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core import designed_pages
from core.models import BlogPost, Page
from core.wp_clean import plain_text

OUT = Path(settings.BASE_DIR) / "import_cache" / "proof"


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **opts):
        OUT.mkdir(parents=True, exist_ok=True)
        pages = []
        for page in Page.objects.filter(is_published=True).order_by("path", "slug"):
            url = page.get_absolute_url()
            text_parts = [
                plain_text(part)
                for part in (page.hero_html, page.body, page.after_html)
                if plain_text(part)
            ]
            pages.append({
                "url": url,
                "title": page.title,
                "designed": url in designed_pages.SPECS and url not in ("/our-team/", "/testimonials/"),
                "text": text_parts,
            })
        (OUT / "pages.json").write_text(json.dumps(pages))
        posts = [
            {"url": p.get_absolute_url(), "title": p.title, "text": [plain_text(p.body)]}
            for p in BlogPost.objects.filter(is_published=True)
        ]
        (OUT / "posts.json").write_text(json.dumps(posts))
        wp = [p for p in pages if not p["designed"]]
        words = lambda items: sum(len(" ".join(i["text"]).split()) for i in items)
        self.stdout.write(
            f"{len(pages)} pages ({len(wp)} from WordPress, {words(wp)} words); "
            f"{len(posts)} posts ({words(posts)} words)"
        )
