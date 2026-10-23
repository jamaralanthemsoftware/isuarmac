"""Build the plain-Django ISU-ARMAC site from the WordPress export in import_cache/.

Re-runnable: --reset deletes imported pages, posts, topics, team and redirects first.
Pages with a hand-built design (homepage, contractor, hospital, industries, hubs, forms) come from
core/designed_pages.py; every other page is converted from its WordPress content.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import Truncator
from django.utils.timezone import make_aware

from core import designed_pages
from core.content_fixes import apply_fixes, unapplied_page_fixes
from core.middleware import LEGACY_WORDPRESS_REDIRECTS
from core.models import (
    BlogPost,
    BlogTopic,
    FAQ,
    LegacyRedirect,
    Page,
    SiteSettings,
    TeamMember,
)
from core.navigation import SITE_INFO
from core.page_builder import DEFAULT_TEAM, add_plugin, make_placeholders
from core.wp_clean import clean_fragment, clean_title, page_blocks, plain_text, site_path

CACHE = Path(settings.BASE_DIR) / "import_cache"
LANG = "en"

REDIRECTS = {
    **LEGACY_WORDPRESS_REDIRECTS,
}
# Served by dedicated Django views instead of Page records.
VIEW_PATHS = {"/blog/", "/site-map/", "/contact/", "/services/", "/about/", "/faq/"}

TEAM = DEFAULT_TEAM

DROP_HEADINGS = re.compile(r"(get started below|ready to get a quote|request a quote below)", re.I)


def drop_repeated_paragraphs(blocks):
    """Some WordPress pages repeat whole sections; keep only the first copy of any long paragraph."""
    seen, out = set(), []
    for kind, value in blocks:
        if kind == "html":
            soup = BeautifulSoup(value, "lxml")
            for el in soup.find_all(["p", "li", "h2", "h3"]):
                key = " ".join(el.get_text(" ").split())
                if len(key) > 60:
                    if key in seen:
                        el.decompose()
                    else:
                        seen.add(key)
            body = soup.body or soup
            value = "".join(str(c) for c in body.contents)
        out.append((kind, value))
    return out


def path_of(link):
    return site_path(link)


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Skip import if pages already exist in the database.",
        )
        parser.add_argument(
            "--fetch",
            action="store_true",
            help="Fetch WordPress REST API and SEO metadata into import_cache/ before importing.",
        )

    def handle(self, *args, reset=False, if_empty=False, fetch=False, **opts):
        import gzip
        from django.core.management import call_command

        if if_empty and Page.objects.filter(slug="home").exists():
            self.stdout.write("ISU-ARMAC content already imported; skipping.")
            return

        bundle_path = Path(settings.BASE_DIR) / "core" / "wp_bundle.json.gz"
        if fetch:
            call_command("fetch_wordpress")
            call_command("fetch_seo")

        self.images = set()
        self.report = {"pages": [], "posts": 0, "redirects": 0, "notes": []}

        if (CACHE / "pages.json").exists() and not fetch:
            seo_path = CACHE / "seo.json"
            self.seo = json.loads(seo_path.read_text()) if seo_path.exists() else {}
            wp_pages = json.loads((CACHE / "pages.json").read_text())
            posts = json.loads((CACHE / "posts.json").read_text())
            categories = json.loads((CACHE / "categories.json").read_text())
            media = {m["id"]: m for m in json.loads((CACHE / "media.json").read_text())}
        elif bundle_path.exists() and not fetch:
            bundle = json.loads(gzip.decompress(bundle_path.read_bytes()).decode("utf-8"))
            self.seo = bundle.get("seo", {})
            wp_pages = bundle["pages"]
            posts = bundle["posts"]
            categories = bundle["categories"]
            media = {m["id"]: m for m in bundle["media"]}
        else:
            call_command("fetch_wordpress")
            call_command("fetch_seo")
            seo_path = CACHE / "seo.json"
            self.seo = json.loads(seo_path.read_text()) if seo_path.exists() else {}
            wp_pages = json.loads((CACHE / "pages.json").read_text())
            posts = json.loads((CACHE / "posts.json").read_text())
            categories = json.loads((CACHE / "categories.json").read_text())
            media = {m["id"]: m for m in json.loads((CACHE / "media.json").read_text())}

        with transaction.atomic():
            if reset:
                self.reset()
            self.import_site_settings()
            self.import_team()
            self.import_posts(posts, categories, media)
            self.import_pages(wp_pages)
            self.import_redirects()
        self.report["unapplied_page_fixes"] = unapplied_page_fixes()
        try:
            CACHE.mkdir(exist_ok=True)
            (CACHE / "images.json").write_text(json.dumps(sorted(self.images)))
            (CACHE / "import_report.json").write_text(json.dumps(self.report, indent=1))
        except OSError:
            pass
        self.stdout.write(
            f"pages {len(self.report['pages'])}, posts {self.report['posts']}, "
            f"redirects {self.report['redirects']}, images to download {len(self.images)}, "
            f"page fixes not matched {len(self.report['unapplied_page_fixes'])}"
        )

    def reset(self):
        Page.objects.all().delete()
        BlogPost.objects.all().delete()
        BlogTopic.objects.all().delete()
        TeamMember.objects.all().delete()
        LegacyRedirect.objects.all().delete()

    def import_site_settings(self):
        settings_obj = SiteSettings.objects.first() or SiteSettings()
        settings_obj.site_name = SITE_INFO["name"]
        settings_obj.contact_email = SITE_INFO["email"]
        settings_obj.contact_phone = SITE_INFO["phone_ca"]
        settings_obj.address = "\n".join(SITE_INFO["address_lines"])
        if not settings_obj.default_meta_description:
            settings_obj.default_meta_description = (
                "ISU-ARMAC shops 300+ carriers for personal, commercial, contractor, hospital, "
                "and employee benefits insurance across California, Nevada, Arizona, and nationwide."
            )
        settings_obj.save()

    def import_team(self):
        for order, (name, title, photo, featured) in enumerate(TEAM):
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            square = Path(settings.BASE_DIR) / "static" / "img" / "team" / f"{slug}.jpg"
            photo_url = f"/static/img/team/{slug}.jpg" if square.exists() else f"/media/uploads/{photo}"
            TeamMember.objects.update_or_create(
                name=name,
                defaults={
                    "title": title,
                    "photo_url": photo_url,
                    "order": order,
                    "featured": featured,
                },
            )
            self.images.add(f"https://isu-armac.com/wp-content/uploads/{photo}")
        if not TEAM[-1][1]:
            self.report["notes"].append("Rebecca Scharnberg has no job title on the current Our Team page.")

    def seo_for(self, link):
        data = self.seo.get(link, {})
        return apply_fixes(data.get("title", ""), brand=False), apply_fixes(data.get("description", ""))

    def _crumbs_for(self, parent: Page | None, current_label: str) -> list[tuple[str, str | None]]:
        crumbs = []
        curr = parent
        ancestors = []
        visited = set()
        while curr is not None and curr.pk not in visited:
            visited.add(curr.pk)
            if curr.slug != "home" and curr.path != "/":
                ancestors.append((curr.menu_title or curr.title, curr.get_absolute_url()))
            curr = curr.parent
        crumbs.extend(reversed(ancestors))
        crumbs.append((current_label, None))
        return crumbs

    def import_pages(self, wp_pages):
        by_path = {path_of(p["link"]): p for p in wp_pages}
        paths = sorted(set(by_path) | set(designed_pages.NEW_PAGES), key=lambda p: (p.count("/"), p))
        created = {}
        for path in paths:
            if path in REDIRECTS or path in VIEW_PATHS:
                continue
            wp = by_path.get(path)
            parent_path = "/" if path.count("/") <= 2 else path.rsplit("/", 2)[0] + "/"
            parent = None if path == "/" or parent_path == "/" else created.get(parent_path)
            if path != "/" and parent_path != "/" and parent is None:
                self.report["notes"].append(f"No parent for {path}; placed at top level")
            spec = designed_pages.spec_for(path)
            raw_title = wp["title"]["rendered"] if wp else spec["title"]
            title = apply_fixes(spec.get("title") or clean_title(raw_title))
            seo_title, seo_desc = self.seo_for(wp["link"]) if wp else ("", "")
            if spec.get("seo_title"):
                seo_title = spec["seo_title"]
            if spec.get("seo_description"):
                seo_desc = spec["seo_description"]
            slug = path.strip("/").split("/")[-1] if path != "/" else "home"
            if slug in Page.RESERVED_SLUGS:
                continue
            template = spec.get("template") or ("home.html" if path == "/" else "detail.html")
            menu_title = spec.get("menu_title") or ""
            crumbs = [] if path == "/" else self._crumbs_for(parent, menu_title or title)
            placeholders = make_placeholders(crumbs=crumbs)
            if spec.get("build"):
                spec["build"](placeholders, wp=wp, ctx=self)
            elif wp:
                self.build_from_wordpress(placeholders, wp, title)

            hero_html = str(placeholders["hero"].render())
            body_html = str(placeholders["content"].render())
            after_html = str(placeholders["after"].render())
            plain_summary = plain_text(seo_desc or body_html)[:300]

            page, _ = Page.objects.update_or_create(
                slug=slug,
                defaults={
                    "title": title[:180],
                    "path": path,
                    "parent": parent,
                    "menu_title": menu_title[:180],
                    "template_name": template,
                    "summary": plain_summary,
                    "hero_html": hero_html,
                    "body": body_html,
                    "after_html": after_html,
                    "meta_title": Truncator(seo_title or title).chars(70),
                    "meta_description": Truncator(seo_desc or plain_summary).chars(160),
                    "is_published": True,
                },
            )
            created[path] = page
            if path == "/about-us/":
                Page.objects.update_or_create(
                    slug="about",
                    defaults={
                        "title": title[:180],
                        "path": "/about/",
                        "template_name": template,
                        "summary": plain_summary,
                        "hero_html": hero_html,
                        "body": body_html,
                        "after_html": after_html,
                        "meta_title": Truncator(seo_title or title).chars(70),
                        "meta_description": Truncator(seo_desc or plain_summary).chars(160),
                        "is_published": True,
                    },
                )
            self.report["pages"].append({
                "path": path,
                "title": title,
                "template": template,
                "designed": bool(spec.get("build")),
            })

        if "/faq/" in by_path and not FAQ.objects.exists():
            wp_faq = by_path["/faq/"]
            order = 0
            for kind, value in page_blocks(wp_faq["content"]["rendered"], "FAQ", self.images):
                if kind == "faq":
                    for q, a in value:
                        FAQ.objects.create(
                            question=apply_fixes(q, url="/faq/")[:240],
                            answer=apply_fixes(plain_text(a), url="/faq/"),
                            is_published=True,
                            display_order=order,
                        )
                        order += 1

        if not FAQ.objects.exists():
            default_faqs = [
                (
                    "Is ISU-ARMAC an insurance company or an independent agency?",
                    "We are an independent insurance agency. Instead of selling one company's policies, we compare quotes from more than 300 insurance companies to find coverage and pricing that fit you. When you have a question or a claim, you call our team directly.",
                ),
                (
                    "Does using an independent agent cost more than buying direct?",
                    "No. Our commission is paid by the insurance company you choose and is already built into the policy rate. Because we shop hundreds of carriers at once, we often find a better price or better coverage than a single company can offer on its own.",
                ),
                (
                    "What states is ISU-ARMAC licensed in?",
                    "Our headquarters are in Victorville, California, with a focus on California, Nevada and Arizona. Through the ISU Insurance Agency Network we are licensed in all 50 states and can insure multi-state businesses and properties.",
                ),
                (
                    "How fast can you issue a certificate of insurance or contractor bond?",
                    "Most certificates of insurance and standard license bonds are issued the same business day—often within a few hours—so your project or job site is not held up.",
                ),
                (
                    "Can one agency handle our business insurance, workers' comp, and employee benefits?",
                    "Yes. ISU-ARMAC has dedicated commercial, contractor, hospital, and employee benefits teams under one roof, so you have one agency coordinating your property, liability, workers' compensation, and group health plans.",
                ),
            ]
            for order, (question, answer) in enumerate(default_faqs):
                FAQ.objects.create(
                    question=question,
                    answer=answer,
                    is_published=True,
                    display_order=order,
                )

    def build_from_wordpress(self, placeholders, wp, title):
        ph = placeholders["content"]
        url = path_of(wp["link"])
        fix = lambda t: apply_fixes(t, url=url)
        designed_pages.industry_hero(placeholders["hero"], url, title)
        blocks = page_blocks(wp["content"]["rendered"], clean_title(wp["title"]["rendered"]), self.images)
        if not blocks:
            self.report["notes"].append(f"{path_of(wp['link'])}: no content found on WordPress page")
        blocks = drop_repeated_paragraphs(blocks)
        for kind, value in blocks:
            if kind == "html":
                value = re.sub(
                    r"<h[23]>[^<]*</h[23]>",
                    lambda m: "" if DROP_HEADINGS.search(m.group(0)) else m.group(0),
                    value,
                )
                if plain_text(value):
                    add_plugin(ph, "TextPlugin", LANG, body=fix(value))
            elif kind == "faq":
                faq = add_plugin(ph, "FAQPlugin", LANG)
                for i, (q, a) in enumerate(value):
                    add_plugin(
                        ph,
                        "FAQItemPlugin",
                        LANG,
                        target=faq,
                        question=fix(q)[:255],
                        answer=fix(plain_text(a)),
                        open=(i == 0),
                    )
            elif kind == "cards":
                grid = add_plugin(ph, "CardGridPlugin", LANG, columns=2 if len(value) % 2 == 0 else 3, style="plain")
                for card_title, text, img in value:
                    add_plugin(
                        ph,
                        "CardPlugin",
                        LANG,
                        target=grid,
                        title=fix(card_title or "")[:255] or "—",
                        text=fix(text),
                        image_url=img,
                    )
            elif kind == "testimonials":
                for quote, who in value:
                    add_plugin(ph, "TestimonialPlugin", LANG, quote=fix(quote), attribution=who)

    def import_posts(self, posts, categories, media):
        cats = {}
        for c in categories:
            if c.get("count"):
                topic, _ = BlogTopic.objects.update_or_create(
                    slug=c["slug"][:100],
                    defaults={"name": c["name"].replace("&amp;", "&")[:100]},
                )
                cats[c["id"]] = topic

        for p in posts:
            if p.get("status") != "publish":
                continue
            content = apply_fixes(clean_fragment(p["content"]["rendered"], self.images))
            featured = ""
            m = media.get(p.get("featured_media"))
            if m and m.get("source_url"):
                featured = site_path(m["source_url"])
                self.images.add(m["source_url"])
            seo_title, seo_desc = self.seo_for(p["link"])
            title = apply_fixes(clean_title(p["title"]["rendered"]) or p["slug"])[:240]
            excerpt = apply_fixes(plain_text(p["excerpt"]["rendered"]))[:500]
            pub_dt = make_aware(datetime.fromisoformat(p["date"]))
            mod_dt = make_aware(datetime.fromisoformat(p["modified"])) if p.get("modified") else pub_dt
            post, _ = BlogPost.objects.update_or_create(
                slug=p["slug"][:240],
                defaults={
                    "title": title,
                    "original_published_at": pub_dt,
                    "original_modified_at": mod_dt,
                    "summary": excerpt,
                    "body": content,
                    "featured_image_url": featured,
                    "meta_title": Truncator(seo_title or title).chars(70),
                    "meta_description": Truncator(seo_desc or excerpt).chars(300),
                    "source_url": p.get("link", "")[:1000],
                    "source_guid": f"wp:post:{p['id']}",
                    "wp_id": p["id"],
                    "is_published": True,
                },
            )
            post.topics.set([cats[c] for c in p.get("categories", []) if c in cats])
            self.report["posts"] += 1

    def import_redirects(self):
        for old, new in REDIRECTS.items():
            LegacyRedirect.objects.update_or_create(old_path=old, defaults={"new_path": new})
            self.report["redirects"] += 1
