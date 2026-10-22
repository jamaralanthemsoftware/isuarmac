from cms.models import CMSPlugin
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool

from . import models

MODULE = "ISU-ARMAC"


class Base(CMSPluginBase):
    module = MODULE
    cache = True


@plugin_pool.register_plugin
class SectionPlugin(Base):
    model = models.Section
    name = "Section"
    render_template = "site_core/plugins/section.html"
    allow_children = True


@plugin_pool.register_plugin
class HeroPlugin(Base):
    model = models.Hero
    name = "Hero"
    render_template = "site_core/plugins/hero.html"


@plugin_pool.register_plugin
class StatsBandPlugin(Base):
    model = CMSPlugin
    name = "Stats band"
    render_template = "site_core/plugins/stats_band.html"
    allow_children = True
    child_classes = ["StatPlugin"]


@plugin_pool.register_plugin
class StatPlugin(Base):
    model = models.Stat
    name = "Stat"
    render_template = "site_core/plugins/stat.html"
    require_parent = True
    parent_classes = ["StatsBandPlugin"]


@plugin_pool.register_plugin
class CardGridPlugin(Base):
    model = models.CardGrid
    name = "Card grid"
    render_template = "site_core/plugins/card_grid.html"
    allow_children = True
    child_classes = ["CardPlugin"]


@plugin_pool.register_plugin
class CardPlugin(Base):
    model = models.Card
    name = "Card"
    render_template = "site_core/plugins/card.html"
    require_parent = True
    parent_classes = ["CardGridPlugin", "SplitPlugin"]

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        parent = instance.parent.get_plugin_instance()[0] if instance.parent_id else None
        context["grid_style"] = getattr(parent, "style", "soft")
        return context


@plugin_pool.register_plugin
class SplitPlugin(Base):
    model = models.Split
    name = "Image and text with points"
    render_template = "site_core/plugins/split.html"
    allow_children = True
    child_classes = ["CardPlugin"]


@plugin_pool.register_plugin
class TeamStripPlugin(Base):
    model = models.TeamStrip
    name = "Team"
    render_template = "site_core/plugins/team_strip.html"
    cache = False

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        members = models.TeamMember.objects.all()
        if not instance.show_all:
            members = members.filter(featured=True)[: instance.count]
        context["members"] = members
        return context


@plugin_pool.register_plugin
class TestimonialPlugin(Base):
    model = models.Testimonial
    name = "Testimonial"
    render_template = "site_core/plugins/testimonial.html"


@plugin_pool.register_plugin
class LatestPostsPlugin(Base):
    model = models.LatestPosts
    name = "Latest blog posts"
    render_template = "site_core/plugins/latest_posts.html"
    cache = False

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        context["posts"] = models.BlogPost.objects.filter(is_published=True)[: instance.count]
        return context


@plugin_pool.register_plugin
class CTABandPlugin(Base):
    model = models.CTABand
    name = "Call-to-action band"
    render_template = "site_core/plugins/cta_band.html"


@plugin_pool.register_plugin
class CalloutPlugin(Base):
    model = models.Callout
    name = "Callout box"
    render_template = "site_core/plugins/callout.html"


@plugin_pool.register_plugin
class PillListPlugin(Base):
    model = models.PillList
    name = "Pill links"
    render_template = "site_core/plugins/pill_list.html"


@plugin_pool.register_plugin
class FAQPlugin(Base):
    model = CMSPlugin
    name = "FAQ list"
    render_template = "site_core/plugins/faq.html"
    allow_children = True
    child_classes = ["FAQItemPlugin"]


@plugin_pool.register_plugin
class FAQItemPlugin(Base):
    model = models.FAQItem
    name = "FAQ question"
    render_template = "site_core/plugins/faq_item.html"
    require_parent = True
    parent_classes = ["FAQPlugin"]


@plugin_pool.register_plugin
class QuoteFormPlugin(Base):
    model = models.QuoteForm
    name = "Quote form"
    render_template = "site_core/plugins/quote_form.html"
    cache = False

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        from .forms import form_for

        context["form"] = form_for(instance.form_type)
        return context
