import logging
from pathlib import PurePosixPath

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Count, Q, Subquery
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponsePermanentRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, ListView

from anthem_seo.views import managed_page as anthem_managed_page
from .anthem import deliver_lead_to_anthem
from .forms import LeadForm, form_for
from .models import (
    BlogPost,
    BlogTopic,
    DownloadableAsset,
    FAQ,
    Lead,
    LegacyRedirect,
    Page,
    QuoteRequest,
    Service,
)
from .postmark import PostmarkDeliveryError, send_contact_lead_notification
from .recaptcha import get_contact_recaptcha_config, verify_contact_recaptcha

logger = logging.getLogger(__name__)


@never_cache
@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


@require_GET
def robots_txt(request):
    sitemap_url = request.build_absolute_uri(reverse("sitemap"))
    lines = ["User-agent: *", "Allow: /", f"Sitemap: {sitemap_url}"]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def home(request):
    page = Page.objects.filter(slug="home", is_published=True).first()
    return render(
        request,
        "home.html",
        {
            "page": page,
            "services": Service.objects.filter(is_published=True)[:6],
        },
    )


def about(request):
    page = (
        Page.objects.filter(slug="about", is_published=True).first()
        or Page.objects.filter(slug="about-us", is_published=True).first()
    )
    return render(request, "about.html", {"page": page, "object": page})


def services(request):
    return render(
        request,
        "services.html",
        {"services": Service.objects.filter(is_published=True)},
    )


def faq(request):
    page = Page.objects.filter(slug="faq", is_published=True).first()
    return render(
        request,
        "faq.html",
        {"faqs": FAQ.objects.filter(is_published=True), "page": page},
    )


def html_site_map(request):
    pages = Page.objects.filter(is_published=True).exclude(slug="about").order_by("path", "slug")
    entries = []
    for page in pages:
        url = "/" if page.slug == "home" else page.get_absolute_url()
        depth = 1 if url == "/" else max(1, url.strip("/").count("/") + 1)
        entries.append({"title": page.title, "url": url, "depth": depth})
    return render(
        request,
        "site_core/site_map.html",
        {
            "entries": entries,
            "crumbs": [("Site map", None)],
            "post_count": BlogPost.objects.filter(is_published=True).count(),
        },
    )


@never_cache
@require_GET
def download_asset(request, slug):
    asset = get_object_or_404(DownloadableAsset, slug=slug, is_published=True)
    if not asset.file:
        raise Http404("Downloadable file not found.")
    filename = PurePosixPath(asset.file.name).name or asset.slug
    try:
        return FileResponse(
            asset.file.open("rb"),
            as_attachment=True,
            filename=filename,
        )
    except FileNotFoundError as exc:
        raise Http404("Downloadable file not found.") from exc


class PageDetailView(DetailView):
    model = Page
    template_name = "page_detail.html"

    def get_queryset(self):
        return Page.objects.filter(is_published=True)

    def get(self, request, *args, **kwargs):
        slug = kwargs.get("slug", "")
        page = Page.objects.filter(is_published=True, slug=slug).first()
        if page is not None:
            if page.path and page.path not in ("/", f"/{slug}/"):
                return HttpResponsePermanentRedirect(page.path)
            self.object = page
            context = self.get_context_data(object=self.object, page=self.object)
            return self.render_to_response(context)
        post = BlogPost.objects.filter(is_published=True, slug=slug).first()
        if post is not None:
            return BlogDetailView.as_view()(request, slug=slug)
        redirect_obj = LegacyRedirect.objects.filter(old_path=request.path).first()
        if redirect_obj is not None:
            return HttpResponsePermanentRedirect(redirect_obj.new_path)
        raise Http404("No page matches the given query.")


def nested_or_managed_page(request, seo_path):
    try:
        return anthem_managed_page(request, seo_path)
    except Http404:
        pass
    normalized = "/" + seo_path.strip("/") + "/"
    redirect_obj = LegacyRedirect.objects.filter(old_path=normalized).first()
    if redirect_obj is not None:
        return HttpResponsePermanentRedirect(redirect_obj.new_path)
    leaf_slug = normalized.strip("/").split("/")[-1]
    page = (
        Page.objects.filter(is_published=True, path=normalized).first()
        or Page.objects.filter(is_published=True, slug=leaf_slug).first()
    )
    if page is None:
        raise Http404("No page matches the given query.")
    return render(
        request,
        "page_detail.html",
        {"object": page, "page": page},
    )


class ServiceDetailView(DetailView):
    model = Service
    template_name = "service_detail.html"

    def get_queryset(self):
        return Service.objects.filter(is_published=True)


class BlogListView(ListView):
    model = BlogPost
    template_name = "blog/list.html"
    context_object_name = "posts"
    paginate_by = 10

    def get_queryset(self):
        qs = BlogPost.objects.filter(is_published=True)
        category_slug = self.kwargs.get("category")
        if category_slug:
            self.current_category = get_object_or_404(BlogTopic, slug=category_slug)
            qs = qs.filter(topics=self.current_category)
        else:
            self.current_category = None
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current = getattr(self, "current_category", None)
        context["categories"] = BlogTopic.objects.all()
        context["current_category"] = current
        context["crumbs"] = (
            [("Blog", "/blog/"), (current.name, None)]
            if current
            else [("Blog", None)]
        )
        return context


class BlogDetailView(DetailView):
    model = BlogPost
    template_name = "blog/detail.html"

    def get_queryset(self):
        return BlogPost.objects.filter(is_published=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_articles = list(
            BlogPost.objects.filter(
                is_published=True,
                selected_as_related__source_post=self.object,
            )
            .only(
                "title",
                "slug",
                "summary",
                "original_published_at",
                "created_at",
                "featured_image",
                "featured_image_url",
            )
            .order_by("selected_as_related__position")
        )
        remaining_slots = 3 - len(selected_articles)
        topic_ids = self.object.topics.through.objects.filter(
            blogpost_id=self.object.pk
        ).values("blogtopic_id")
        automatic_articles = list(
            BlogPost.objects.filter(is_published=True)
            .exclude(pk__in=[self.object.pk, *(post.pk for post in selected_articles)])
            .annotate(
                shared_topic_count=Count(
                    "topics",
                    filter=Q(topics__in=Subquery(topic_ids)),
                    distinct=True,
                )
            )
            .order_by(
                "-shared_topic_count",
                "-original_published_at",
                "-created_at",
            )
            .only(
                "title",
                "slug",
                "summary",
                "original_published_at",
                "created_at",
                "featured_image",
                "featured_image_url",
            )[:remaining_slots]
        )
        context["related_articles"] = selected_articles + automatic_articles
        return context


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").strip().split(None, 1)
    if not parts:
        return ("Website", "Visitor")
    if len(parts) == 1:
        return (parts[0][:60], "Visitor")
    return (parts[0][:60], parts[1][:60])


@csrf_exempt
@require_POST
def submit_lead(request):
    form = form_for(request.POST.get("form_type", "general"), request.POST)
    if not form.is_valid():
        return render(request, "site_core/form_errors.html", {"form": form}, status=400)
    data = form.cleaned_data
    if data.get("website"):  # honeypot filled in: a bot
        return redirect("/thank-you/")

    details = form.details()
    first_name, last_name = _split_full_name(data["name"])
    detail_lines = [
        f"{k.replace('_', ' ').title()}: {', '.join(v) if isinstance(v, list) else v}"
        for k, v in details.items()
    ]
    if data.get("company"):
        detail_lines.insert(0, f"Company: {data['company']}")
    if data.get("state"):
        detail_lines.append(f"State: {data['state']}")
    if data.get("page_url"):
        detail_lines.append(f"Page: {data['page_url']}")
    if data.get("message"):
        detail_lines.append("")
        detail_lines.append(data["message"])
    combined_message = "\n".join(detail_lines).strip() or f"{data['form_type'].title()} inquiry"

    lead = Lead.objects.create(
        first_name=first_name,
        last_name=last_name,
        email=data["email"],
        phone=data.get("phone", ""),
        message=combined_message[:10000],
        source=f"website:{data['form_type']}"[:120],
        consent_to_contact=True,
    )
    quote_req = QuoteRequest.objects.create(
        form_type=data["form_type"],
        page_url=(data.get("page_url") or "")[:500],
        name=data["name"],
        company=data.get("company", ""),
        email=data["email"],
        phone=data.get("phone", ""),
        state=data.get("state", ""),
        details=details,
        message=data.get("message", ""),
        lead=lead,
    )

    try:
        deliver_lead_to_anthem(lead.pk)
    except Exception:
        logger.exception("Anthem CRM delivery failed for lead %s", lead.pk)

    postmark_sent = False
    try:
        postmark_sent = bool(send_contact_lead_notification(lead))
    except PostmarkDeliveryError:
        logger.exception("Postmark could not deliver notification for lead %s", lead.pk)

    if not postmark_sent:
        body = "\n".join(
            [
                f"Name: {quote_req.name}",
                f"Company: {quote_req.company}",
                f"Email: {quote_req.email}",
                f"Phone: {quote_req.phone}",
                f"State: {quote_req.state}",
                f"Page: {quote_req.page_url}",
            ]
            + [
                f"{k.replace('_', ' ').title()}: {', '.join(v) if isinstance(v, list) else v}"
                for k, v in quote_req.details.items()
            ]
            + ["", quote_req.message, "", request.build_absolute_uri(quote_req.get_admin_url())]
        )
        try:
            send_mail(
                f"New website lead ({quote_req.form_type}) from {quote_req.name}",
                body,
                settings.DEFAULT_FROM_EMAIL,
                getattr(settings, "LEAD_NOTIFICATION_EMAILS", ["info@isu-armac.com"]),
            )
        except Exception:
            logger.exception("Lead notification email failed for quote request %s", quote_req.pk)

    return redirect("/thank-you/")


def _contact_context(form, recaptcha_config):
    return {
        "form": form,
        "recaptcha_enabled": recaptcha_config is not None,
        "recaptcha_site_key": (
            recaptcha_config.site_key if recaptcha_config else ""
        ),
    }


def contact(request):
    recaptcha_config = get_contact_recaptcha_config()
    form = LeadForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not verify_contact_recaptcha(
            request.POST.get("recaptcha_token", ""),
            recaptcha_config,
        ):
            form.add_error(
                None,
                "We could not verify this submission. Please try again.",
            )
            return render(
                request,
                "contact.html",
                _contact_context(form, recaptcha_config),
                status=400,
            )
        lead = form.save(commit=False)
        lead.source = request.POST.get("source", "website")[:120]
        lead.save()
        delivery_warnings = []
        anthem_result = deliver_lead_to_anthem(lead.pk)
        if anthem_result is False:
            logger.warning(
                "Anthem CRM could not confirm delivery for lead %s.",
                lead.pk,
            )
            delivery_warnings.append(
                "we could not sync it to our customer system"
            )
        try:
            send_contact_lead_notification(lead)
        except PostmarkDeliveryError:
            logger.exception(
                "Postmark could not deliver the notification for lead %s.",
                lead.pk,
            )
            delivery_warnings.append(
                "we could not alert our team by email"
            )
        if delivery_warnings:
            messages.warning(
                request,
                "Your message was saved, but "
                + " and ".join(delivery_warnings)
                + ". Please contact us directly if your request is urgent.",
            )
        else:
            messages.success(
                request,
                "Thank you. Your message has been received.",
            )
        return redirect("contact")
    return render(
        request,
        "contact.html",
        _contact_context(form, recaptcha_config),
    )
