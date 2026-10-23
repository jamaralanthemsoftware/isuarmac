"""Pure-Django block builder replacing Django CMS 5 placeholders and plugins."""

from __future__ import annotations

import re
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from .forms import form_for
from .models import BlogPost, TeamMember
from .navigation import SITE_INFO

DEFAULT_TEAM = [
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


def parse_links(raw: str):
    out = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            label, url = line.split("|", 1)
            out.append((label.strip(), url.strip()))
        else:
            out.append((line, "#"))
    return out


def default_team_members(*, show_all=False, count=6):
    members = []
    for name, title, _photo, featured in DEFAULT_TEAM:
        if not show_all and not featured:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        members.append(
            SimpleNamespace(
                name=name,
                title=title,
                photo_src=f"/static/img/team/{slug}.jpg",
                featured=featured,
            )
        )
    return members if show_all else members[:count]


PLUGIN_TEMPLATES = {
    "HeroPlugin": "site_core/plugins/hero.html",
    "StatsBandPlugin": "site_core/plugins/stats_band.html",
    "StatPlugin": "site_core/plugins/stat.html",
    "SectionPlugin": "site_core/plugins/section.html",
    "CardGridPlugin": "site_core/plugins/card_grid.html",
    "CardPlugin": "site_core/plugins/card.html",
    "SplitPlugin": "site_core/plugins/split.html",
    "TeamStripPlugin": "site_core/plugins/team_strip.html",
    "TestimonialPlugin": "site_core/plugins/testimonial.html",
    "LatestPostsPlugin": "site_core/plugins/latest_posts.html",
    "CTABandPlugin": "site_core/plugins/cta_band.html",
    "CalloutPlugin": "site_core/plugins/callout.html",
    "PillListPlugin": "site_core/plugins/pill_list.html",
    "FAQPlugin": "site_core/plugins/faq.html",
    "FAQItemPlugin": "site_core/plugins/faq_item.html",
    "QuoteFormPlugin": "site_core/plugins/quote_form.html",
}

PLUGIN_DEFAULTS = {
    "HeroPlugin": {
        "style": "page",
        "badge": "",
        "heading": "",
        "subheading": "",
        "primary_text": "",
        "primary_url": "",
        "secondary_text": "",
        "secondary_url": "",
        "checklist": "",
        "image_url": "",
        "image_alt": "",
    },
    "SectionPlugin": {
        "background": "white",
        "eyebrow": "",
        "heading": "",
        "intro": "",
        "link_text": "",
        "link_url": "",
        "anchor": "",
        "compact": False,
        "prose": False,
        "two_columns": False,
    },
    "CardGridPlugin": {
        "columns": 3,
        "style": "plain",
    },
    "CardPlugin": {
        "icon": "",
        "badge": "",
        "title": "",
        "text": "",
        "links": "",
        "link_text": "",
        "link_url": "",
        "highlight": False,
        "image_url": "",
        "image_alt": "",
    },
    "SplitPlugin": {
        "eyebrow": "",
        "heading": "",
        "text": "",
        "button_text": "",
        "button_url": "",
        "image_url": "",
        "image_alt": "",
    },
    "TeamStripPlugin": {
        "heading": "Meet the people behind your policy",
        "link_text": "Meet the full team →",
        "link_url": "/our-team/",
        "count": 6,
        "show_all": False,
    },
    "TestimonialPlugin": {
        "quote": "",
        "attribution": "",
    },
    "LatestPostsPlugin": {
        "heading": "From the blog",
        "count": 4,
    },
    "CTABandPlugin": {
        "heading": "",
        "text": "",
        "primary_text": "",
        "primary_url": "",
        "secondary_text": "",
        "secondary_url": "",
    },
    "CalloutPlugin": {
        "eyebrow": "",
        "heading": "",
        "text": "",
        "button_text": "",
        "button_url": "",
    },
    "PillListPlugin": {
        "heading": "",
        "intro": "",
        "items": "",
    },
    "FAQItemPlugin": {
        "question": "",
        "answer": "",
        "open": False,
    },
    "QuoteFormPlugin": {
        "form_type": "general",
        "heading": "Get a quote",
        "intro": "A licensed agent will follow up within one business day.",
        "button_text": "Submit",
        "dark": True,
    },
}


class BlockNode:
    def __init__(self, plugin_type: str, placeholder: Placeholder, parent: BlockNode | None = None, **kwargs):
        self.plugin_type = plugin_type
        self.placeholder = placeholder
        self.parent = parent
        self.child_plugin_instances: list[BlockNode] = []
        defaults = dict(PLUGIN_DEFAULTS.get(plugin_type, {}))
        defaults.update(kwargs)
        for key, value in defaults.items():
            setattr(self, key, value)

    @property
    def image_src(self):
        return getattr(self, "image_url", "")

    @property
    def checklist_items(self):
        checklist = getattr(self, "checklist", "") or ""
        return [line.strip() for line in checklist.splitlines() if line.strip()]

    @property
    def link_list(self):
        return parse_links(getattr(self, "links", ""))

    @property
    def item_list(self):
        return parse_links(getattr(self, "items", ""))

    def render(self, base_context: dict | None = None) -> str:
        if self.plugin_type == "TextPlugin":
            return mark_safe(getattr(self, "body", ""))
        template_name = PLUGIN_TEMPLATES[self.plugin_type]
        ctx = {
            "site": SITE_INFO,
            "crumbs": self.placeholder.crumbs,
            **(base_context or {}),
            "instance": self,
        }
        if self.plugin_type == "CardPlugin":
            ctx["grid_style"] = getattr(self.parent, "style", "soft") if self.parent else "soft"
        elif self.plugin_type == "TeamStripPlugin":
            qs = TeamMember.objects.all()
            if not self.show_all:
                qs = qs.filter(featured=True)[: self.count]
            members = list(qs)
            if not members:
                members = default_team_members(show_all=self.show_all, count=self.count)
            ctx["members"] = members
        elif self.plugin_type == "LatestPostsPlugin":
            ctx["posts"] = list(BlogPost.objects.filter(is_published=True)[: self.count])
        elif self.plugin_type == "QuoteFormPlugin":
            ctx["form"] = form_for(self.form_type)
        return render_to_string(template_name, ctx)


class Placeholder:
    def __init__(self, slot: str, crumbs: list[tuple[str, str | None]] | None = None):
        self.slot = slot
        self.crumbs = crumbs or []
        self.root_plugins: list[BlockNode] = []

    def render(self, base_context: dict | None = None) -> str:
        return mark_safe("".join(plugin.render(base_context) for plugin in self.root_plugins))


def make_placeholders(crumbs: list[tuple[str, str | None]] | None = None) -> dict[str, Placeholder]:
    return {
        slot: Placeholder(slot, crumbs=crumbs)
        for slot in ("hero", "content", "sidebar", "after")
    }


def add_plugin(placeholder: Placeholder, plugin_type: str, language: str = "en", target: BlockNode | None = None, **kwargs) -> BlockNode:
    node = BlockNode(plugin_type, placeholder=placeholder, parent=target, **kwargs)
    if target is not None:
        target.child_plugin_instances.append(node)
    else:
        placeholder.root_plugins.append(node)
    return node
