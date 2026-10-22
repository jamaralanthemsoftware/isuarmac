"""Export the visible text of every page and post to import_cache/proof/ for proofreading."""
import json
from pathlib import Path

from cms.models import Page
from django.conf import settings
from django.core.management.base import BaseCommand

from site_core import designed_pages
from site_core.models import BlogPost
from site_core.wp_clean import plain_text

OUT = Path(settings.BASE_DIR) / "import_cache" / "proof"
FIELDS = ("body", "heading", "intro", "subheading", "title", "text", "question", "answer", "quote", "label", "eyebrow")


def page_text(page):
    out = []
    for ph in page.get_content_obj("en").get_placeholders():
        for p in ph.get_plugins("en").order_by("position"):
            inst, _ = p.get_plugin_instance()
            if inst is None:
                continue
            for f in FIELDS:
                v = getattr(inst, f, None)
                if isinstance(v, str) and v.strip():
                    out.append(plain_text(v) if "<" in v else v.strip())
    return out


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **opts):
        OUT.mkdir(parents=True, exist_ok=True)
        pages = []
        for page in Page.objects.filter(is_page_type=False).order_by("path"):
            url = page.get_absolute_url("en")
            pages.append({"url": url, "title": page.get_content_obj("en").title,
                          "designed": url in designed_pages.SPECS and url not in ("/our-team/", "/testimonials/"),
                          "text": page_text(page)})
        (OUT / "pages.json").write_text(json.dumps(pages))
        posts = [{"url": p.get_absolute_url(), "title": p.title, "text": [plain_text(p.content)]} for p in BlogPost.objects.all()]
        (OUT / "posts.json").write_text(json.dumps(posts))
        wp = [p for p in pages if not p["designed"]]
        words = lambda items: sum(len(" ".join(i["text"]).split()) for i in items)
        self.stdout.write(f"{len(pages)} pages ({len(wp)} from WordPress, {words(wp)} words); {len(posts)} posts ({words(posts)} words)")
