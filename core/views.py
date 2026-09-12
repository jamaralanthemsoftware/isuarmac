import logging

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET
from django.views.generic import DetailView

from .forms import LeadForm
from .anthem import deliver_lead_to_anthem
from .models import FAQ, Page, Service
from .postmark import PostmarkDeliveryError, send_contact_lead_notification
from .recaptcha import get_contact_recaptcha_config, verify_contact_recaptcha

logger = logging.getLogger(__name__)


@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


@require_GET
def robots_txt(request):
    lines = ["User-agent: *", "Allow: /", "Sitemap: /sitemap.xml"]
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
