from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET
from django.views.generic import DetailView

from .forms import LeadForm
from .models import Page, Service


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


def contact(request):
    form = LeadForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        lead = form.save(commit=False)
        lead.source = request.POST.get("source", "website")[:120]
        lead.save()
        messages.success(request, "Thank you. Your message has been received.")
        return redirect("contact")
    return render(request, "contact.html", {"form": form})
