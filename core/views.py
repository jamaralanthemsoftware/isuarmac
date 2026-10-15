import logging
from pathlib import PurePosixPath

from django.contrib import messages
from django.db.models import Count, Q, Subquery
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.views.generic import DetailView, ListView

from .forms import LeadForm
from .anthem import deliver_lead_to_anthem
from .models import BlogPost, DownloadableAsset, FAQ, Page, Service
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
    return render(
        request,
        "home.html",
        {"services": Service.objects.filter(is_published=True)[:6]},
    )


def about(request):
    page = Page.objects.filter(slug="about", is_published=True).first()
    return render(request, "about.html", {"page": page})


def services(request):
    return render(
        request,
        "services.html",
        {"services": Service.objects.filter(is_published=True)},
    )


def faq(request):
    return render(
        request,
        "faq.html",
        {"faqs": FAQ.objects.filter(is_published=True)},
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
        return BlogPost.objects.filter(is_published=True)


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
            )[:remaining_slots]
        )
        context["related_articles"] = selected_articles + automatic_articles
        return context


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
