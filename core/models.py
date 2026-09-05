from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SiteSettings(TimeStampedModel):
    site_name = models.CharField(max_length=120, default="Client Website")
    tagline = models.CharField(max_length=180, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    default_meta_description = models.CharField(max_length=300, blank=True)
    footer_disclaimer = models.TextField(blank=True)
    analytics_measurement_id = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name_plural = "site settings"

    def clean(self):
        if self.pk is None and SiteSettings.objects.exists():
            raise ValidationError("Only one SiteSettings record is allowed.")

    def __str__(self):
        return self.site_name


class PublishableModel(TimeStampedModel):
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    summary = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    @property
    def seo_title(self):
        return self.meta_title or self.title

    @property
    def seo_description(self):
        return self.meta_description or self.summary

    def __str__(self):
        return self.title


class Page(PublishableModel):
    show_in_navigation = models.BooleanField(default=False)
    navigation_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["navigation_order", "title"]

    def get_absolute_url(self):
        return reverse("page-detail", kwargs={"slug": self.slug})


class Service(PublishableModel):
    call_to_action_label = models.CharField(max_length=80, blank=True)
    call_to_action_url = models.URLField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "title"]

    def get_absolute_url(self):
        return reverse("service-detail", kwargs={"slug": self.slug})


class Lead(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        CLOSED = "closed", "Closed"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    message = models.TextField()
    source = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    consent_to_contact = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.email})"


class DownloadableAsset(TimeStampedModel):
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="downloads/%Y/%m/")
    is_published = models.BooleanField(default=False)

    def __str__(self):
        return self.title
