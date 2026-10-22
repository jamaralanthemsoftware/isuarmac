import logging

from cms.models import Page
from cms.views import details as cms_details
from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import form_for
from .models import BlogCategory, BlogPost, QuoteRequest

log = logging.getLogger(__name__)


@require_POST
def submit_lead(request):
    form = form_for(request.POST.get("form_type", "general"), request.POST)
    if not form.is_valid():
        return render(request, "site_core/form_errors.html", {"form": form}, status=400)
    data = form.cleaned_data
    if data.get("website"):  # honeypot filled in: a bot
        return redirect("/thank-you/")
    lead = QuoteRequest.objects.create(
        form_type=data["form_type"],
        page_url=(data.get("page_url") or "")[:500],
        name=data["name"],
        company=data.get("company", ""),
        email=data["email"],
        phone=data.get("phone", ""),
        state=data.get("state", ""),
        details=form.details(),
        message=data.get("message", ""),
    )
    body = "\n".join(
        [f"Name: {lead.name}", f"Company: {lead.company}", f"Email: {lead.email}", f"Phone: {lead.phone}",
         f"State: {lead.state}", f"Page: {lead.page_url}"]
        + [f"{k.replace('_', ' ').title()}: {', '.join(v) if isinstance(v, list) else v}" for k, v in lead.details.items()]
        + ["", lead.message, "", request.build_absolute_uri(lead.get_admin_url())]
    )
    try:
        send_mail(f"New website lead ({lead.form_type}) from {lead.name}",
                  body, settings.DEFAULT_FROM_EMAIL, settings.LEAD_NOTIFICATION_EMAILS)
    except Exception:  # the lead is saved either way; email trouble must not lose it
        log.exception("Lead notification email failed for lead %s", lead.pk)
    return redirect("/thank-you/")


def blog_index(request, category=None):
    posts = BlogPost.objects.filter(is_published=True)
    current = None
    if category:
        current = get_object_or_404(BlogCategory, slug=category)
        posts = posts.filter(categories=current)
    page = Paginator(posts, 12).get_page(request.GET.get("page"))
    return render(request, "site_core/blog_index.html", {
        "page_obj": page, "categories": BlogCategory.objects.all(), "current_category": current,
        "crumbs": [("Blog", "/blog/"), (current.name, None)] if current else [("Blog", None)],
    })


def post_or_page(request, slug):
    """Blog posts keep their old root-level URLs (/post-slug/); anything else is a CMS page."""
    post = BlogPost.objects.filter(slug=slug, is_published=True).first()
    if post:
        related = BlogPost.objects.filter(is_published=True).exclude(pk=post.pk)[:3]
        return render(request, "site_core/blog_post.html", {"post": post, "related": related})
    return cms_details(request, slug)


def html_site_map(request):
    pages = (Page.objects.filter(site_id=settings.SITE_ID, is_page_type=False)
             .order_by("path"))
    entries = []
    for page in pages:
        content = page.get_content_obj("en")
        if not content:
            continue
        entries.append({"title": content.title, "url": page.get_absolute_url("en"), "depth": page.depth})
    return render(request, "site_core/site_map.html", {"entries": entries, "crumbs": [("Site map", None)],
                                                       "post_count": BlogPost.objects.filter(is_published=True).count()})

