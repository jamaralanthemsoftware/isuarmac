"""Build the Django CMS site from the WordPress export in import_cache/.

Re-runnable: --reset deletes imported pages, posts, team and redirects first.
Pages with a hand-built design (homepage, contractor, hospital, industries, hubs, forms) come from
site_core/designed_pages.py; every other page is converted from its WordPress content.
"""
import json
import re
from datetime import datetime
from pathlib import Path

from cms.api import add_plugin, create_page
from cms.models import Page
from django.conf import settings
from django.contrib.redirects.models import Redirect
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.timezone import make_aware

from site_core import designed_pages
from site_core.content_fixes import apply_fixes, unapplied_page_fixes
from site_core.models import BlogCategory, BlogPost, TeamMember
from site_core.wp_clean import clean_fragment, clean_title, page_blocks, plain_text, site_path

CACHE = Path(settings.BASE_DIR) / "import_cache"
LANG = "en"

# Duplicate or retired WordPress pages: kept working as permanent redirects.
REDIRECTS = {
    "/about/": "/about-us/",
    "/staff/": "/our-team/",
    "/tell-a-friend/": "/refer-a-friend/",
    "/welcome-to-insurance-company/": "/",
    "/services/": "/insurance-center/service/",
    "/service/": "/insurance-center/service/",
    "/service/flood-insurance/": "/insurance-center/service/personal-lines-insurance/flood-insurance/",
    "/service/vacant-land-insurance/": "/insurance-center/service/commercial-insurance/vacant-land-insurance/",
    "/service/boat-insurance/": "/insurance-center/service/personal-lines-insurance/boat-insurance/",
    "/service/motorcycle-insurance/": "/insurance-center/service/personal-lines-insurance/motorcycle-insurance/",
    "/service/annuities/": "/annuities/",
    "/service/high-fire-risk-insurance/": "/insurance-center/service/private-client-insurance/high-fire-risk-insurance/",
    "/service/watercraft-insurance/": "/insurance-center/service/personal-lines-insurance/boat-insurance/",
    "/service/umbrella-insurance/": "/insurance-center/service/private-client-insurance/umbrella-insurance/",
    "/service/valuable-possessions-insurance/": "/insurance-center/service/private-client-insurance/valuable-possessions-insurance/",
    "/service/secondary-home-insurance/": "/insurance-center/service/private-client-insurance/secondary-home-insurance/",
    "/service/renters-insurance/": "/insurance-center/service/private-client-insurance/renters-insurance/",
    "/service/individual-life-insurance/": "/insurance-center/service/private-client-insurance/individual-life-insurance/",
    "/service/high-net-worth-insurance/": "/insurance-center/service/private-client-insurance/high-net-worth-insurance/",
    "/service/life-insurance/": "/insurance-center/service/private-client-insurance/individual-life-insurance/",
    "/service/business-insurance/": "/insurance-center/service/commercial-insurance/",
    "/service/home-insurance/": "/insurance-center/service/personal-lines-insurance/home-insurance/",
    "/service/health-insurance/": "/insurance-center/products/health-insurance/",
}
# Served by Django views instead of CMS pages.
VIEW_PATHS = {"/blog/", "/site-map/"}

TEAM = [  # (name, title, photo upload path) in the order shown on the Our Team page
    ("Ryan McEachron", "CEO", "2021/08/152_JxwGF9BBnh-Y5sz40rv6ae6W0RytHm0q.jpg", True),
    ("Tami Pickens", "President", "2021/08/155_8bBpJqhbt-ulgEP5X5FMDIfVGK3s6X9e.jpg", True),
    ("Barbara McEachron", "Chief Financial Officer", "2021/08/139_tjA3jjqd8itl94djT5JjaBq9V6y-yqXI.jpg", True),
    ("Jessica Stewart", "VP of Sales, Personal Lines", "2021/08/146_KO40_ZBsVvw9GiiJLpRMNw1D4xVQIqyO.jpg", False),
    ("Jennifer Britzman", "Account Executive and Benefits Manager", "2021/08/145_WBDJbvP42PGatCTG1w9LS3nROLi1TbCQ.jpg", True),
    ("Marina Arellano", "Senior Account Manager", "2021/08/150_j7xM-Xu7qHZRMPWr4ZKeIy9P_3QvqiR_.jpg", True),
    ("Haley Klein", "Commercial Lines Account Executive", "2022/01/haley1.webp", False),
    ("Autumn Pickens", "Commercial Lines Account Representative", "2022/01/Autumn-20242.jpg.webp", True),
    ("Tonja White", "Benefits Account Representative", "2022/03/Tonja-2022.jpg", False),
    ("Kelli C. Firestone", "Personal Lines Account Representative", "2023/04/Kelli-2-scaled.jpg", False),
    ("Christina Hammond", "Personal Lines Account Representative", "2022/11/Christina-Hammond.jpg", False),
    ("Anne Sanboonsiri", "Personal Account Representative", "2022/01/anne1.webp", False),
    ("Preston Pickens", "Personal Account Representative", "2025/10/Preston-1.jpg", False),
    ("Megan Matus", "Director of First Impressions", "2024/03/Megan.jpg", False),
    ("Rebecca Scharnberg", "", "2024/03/Rebecca.jpg", False),
]

DROP_HEADINGS = re.compile(r"(get started below|ready to get a quote|request a quote below)", re.I)


def drop_repeated_paragraphs(blocks):
    """Some WordPress pages repeat whole sections; keep only the first copy of any long paragraph."""
    from bs4 import BeautifulSoup
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

    def handle(self, *args, reset=False, **opts):
        self.images = set()
        self.report = {"pages": [], "posts": 0, "redirects": 0, "notes": []}
        self.seo = json.loads((CACHE / "seo.json").read_text())
        wp_pages = json.loads((CACHE / "pages.json").read_text())
        posts = json.loads((CACHE / "posts.json").read_text())
        categories = json.loads((CACHE / "categories.json").read_text())
        media = {m["id"]: m for m in json.loads((CACHE / "media.json").read_text())}
        with transaction.atomic():
            if reset:
                self.reset()
            self.import_team()
            self.import_pages(wp_pages)
            self.import_posts(posts, categories, media)
            self.import_redirects()
        self.report["unapplied_page_fixes"] = unapplied_page_fixes()
        (CACHE / "images.json").write_text(json.dumps(sorted(self.images)))
        (CACHE / "import_report.json").write_text(json.dumps(self.report, indent=1))
        self.stdout.write(f"pages {len(self.report['pages'])}, posts {self.report['posts']}, "
                          f"redirects {self.report['redirects']}, images to download {len(self.images)}, "
                          f"page fixes not matched {len(self.report['unapplied_page_fixes'])}")

    # ------------------------------------------------------------------
    def reset(self):
        for page in Page.objects.filter(depth=1):
            page.delete()
        Page.objects.all().delete()
        BlogPost.objects.all().delete()
        BlogCategory.objects.all().delete()
        TeamMember.objects.all().delete()
        Redirect.objects.all().delete()

    def import_team(self):
        for order, (name, title, photo, featured) in enumerate(TEAM):
            TeamMember.objects.create(name=name, title=title, photo_url=f"/media/uploads/{photo}", order=order, featured=featured)
            self.images.add(f"https://isu-armac.com/wp-content/uploads/{photo}")
        if not TEAM[-1][1]:
            self.report["notes"].append("Rebecca Scharnberg has no job title on the current Our Team page.")

    # ------------------------------------------------------------------
    def seo_for(self, link):
        data = self.seo.get(link, {})
        return apply_fixes(data.get("title", ""), brand=False), apply_fixes(data.get("description", ""))

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
            template = spec.get("template") or ("home.html" if path == "/" else "detail.html")
            page = create_page(
                title=title, template=template, language=LANG, slug=slug, parent=parent,
                in_navigation=False, page_title=seo_title or None,
                meta_description=(seo_desc or "")[:320] or None,
                menu_title=spec.get("menu_title"),
            )
            if path == "/":
                page.set_as_homepage()
            created[path] = page
            content = page.get_content_obj(LANG)
            placeholders = {ph.slot: ph for ph in content.get_placeholders()}
            if spec.get("build"):
                spec["build"](placeholders, wp=wp, ctx=self)
            elif wp:
                self.build_from_wordpress(placeholders, wp, title)
            self.report["pages"].append({"path": path, "title": title, "template": template,
                                         "designed": bool(spec.get("build"))})

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
                value = re.sub(r"<h[23]>[^<]*</h[23]>", lambda m: "" if DROP_HEADINGS.search(m.group(0)) else m.group(0), value)
                if plain_text(value):
                    add_plugin(ph, "TextPlugin", LANG, body=fix(value))
            elif kind == "faq":
                faq = add_plugin(ph, "FAQPlugin", LANG)
                for i, (q, a) in enumerate(value):
                    add_plugin(ph, "FAQItemPlugin", LANG, target=faq, question=fix(q)[:255],
                               answer=fix(plain_text(a)), open=(i == 0))
            elif kind == "cards":
                grid = add_plugin(ph, "CardGridPlugin", LANG, columns=2 if len(value) % 2 == 0 else 3, style="plain")
                for card_title, text, img in value:
                    add_plugin(ph, "CardPlugin", LANG, target=grid, title=fix(card_title or "")[:255] or "—",
                               text=fix(text), image_url=img)
            elif kind == "testimonials":
                for quote, who in value:
                    add_plugin(ph, "TestimonialPlugin", LANG, quote=fix(quote), attribution=who)

    # ------------------------------------------------------------------
    def import_posts(self, posts, categories, media):
        cats = {c["id"]: BlogCategory.objects.create(name=c["name"].replace("&amp;", "&"), slug=c["slug"])
                for c in categories if c.get("count")}
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
            post = BlogPost.objects.create(
                title=apply_fixes(clean_title(p["title"]["rendered"]) or p["slug"]),
                slug=p["slug"][:200],
                published=make_aware(datetime.fromisoformat(p["date"])),
                excerpt=apply_fixes(plain_text(p["excerpt"]["rendered"]))[:1000],
                content=content,
                featured_image_url=featured,
                seo_title=seo_title, seo_description=seo_desc,
                wp_id=p["id"],
            )
            post.categories.set([cats[c] for c in p.get("categories", []) if c in cats])
            self.report["posts"] += 1

    def import_redirects(self):
        site = Site.objects.get(pk=settings.SITE_ID)
        for old, new in REDIRECTS.items():
            Redirect.objects.update_or_create(site=site, old_path=old, defaults={"new_path": new})
            self.report["redirects"] += 1
