import base64
import hashlib
import re
from decimal import Decimal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, validate_email
from django.db import models
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.text import Truncator


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
    default_open_graph_title = models.CharField(max_length=70, blank=True)
    default_open_graph_description = models.CharField(max_length=200, blank=True)
    default_open_graph_image = models.FileField(
        upload_to="open-graph/%Y/%m/",
        blank=True,
    )
    footer_disclaimer = models.TextField(blank=True)
    analytics_measurement_id = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name_plural = "site settings"

    def clean(self):
        if self.pk is None and SiteSettings.objects.exists():
            raise ValidationError("Only one SiteSettings record is allowed.")

    def __str__(self):
        return self.site_name


def _recaptcha_cipher():
    digest = hashlib.sha256(
        f"django-cms-template:recaptcha:{settings.SECRET_KEY}".encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _postmark_cipher():
    digest = hashlib.sha256(
        f"django-cms-template:postmark:{settings.SECRET_KEY}".encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _anthem_cipher():
    digest = hashlib.sha256(
        f"django-cms-template:anthem-crm:{settings.SECRET_KEY}".encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def validate_anthem_webhook_url(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "live.anthemcrm.com"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(
            r"/api/v1/organization/\d+/gravity-forms-webhook/",
            parsed.path,
        )
    ):
        raise ValidationError(
            "Enter an HTTPS Anthem CRM Gravity Forms webhook URL from live.anthemcrm.com."
        )


class RecaptchaIntegration(TimeStampedModel):
    singleton_key = models.CharField(
        max_length=20,
        unique=True,
        default="default",
        editable=False,
    )
    site_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="The public Google reCAPTCHA v3 site key.",
    )
    secret_key_encrypted = models.TextField(blank=True, editable=False)
    minimum_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.80"),
        help_text="Reject scores below this value. The template default is 0.80.",
    )
    allowed_hostnames = models.TextField(
        blank=True,
        help_text="One permanent hostname per line, without https:// or a path.",
    )
    is_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Enable reCAPTCHA v3 on the public contact form only after the permanent "
            "domain, site key, secret key, and allowed hostnames are configured."
        ),
    )

    class Meta:
        verbose_name = "reCAPTCHA integration"
        verbose_name_plural = "reCAPTCHA integration"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    minimum_score__gte=Decimal("0"),
                    minimum_score__lte=Decimal("1"),
                ),
                name="recaptcha_minimum_score_between_zero_and_one",
            )
        ]

    @property
    def normalized_hostnames(self):
        return {
            hostname.strip().lower()
            for hostname in self.allowed_hostnames.replace(",", "\n").splitlines()
            if hostname.strip()
        }

    @property
    def secret_key_configured(self):
        return bool(self.secret_key_encrypted)

    def set_secret_key(self, secret_key):
        value = secret_key.strip()
        self.secret_key_encrypted = (
            _recaptcha_cipher().encrypt(value.encode()).decode() if value else ""
        )

    def get_secret_key(self):
        if not self.secret_key_encrypted:
            return ""
        try:
            return (
                _recaptcha_cipher()
                .decrypt(self.secret_key_encrypted.encode())
                .decode()
            )
        except (InvalidToken, ValueError, TypeError, UnicodeDecodeError):
            return ""

    def clean(self):
        if self.pk is None and RecaptchaIntegration.objects.exists():
            raise ValidationError("Only one reCAPTCHA integration is allowed.")
        if (
            self.minimum_score is not None
            and not Decimal("0") <= self.minimum_score <= Decimal("1")
        ):
            raise ValidationError(
                {"minimum_score": "Enter a score between 0.00 and 1.00."}
            )
        invalid_hostnames = [
            hostname
            for hostname in self.normalized_hostnames
            if not re.fullmatch(
                r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
                r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
                hostname,
            )
        ]
        if invalid_hostnames:
            raise ValidationError(
                {"allowed_hostnames": "Enter valid hostnames only."}
            )

    def __str__(self):
        return "reCAPTCHA integration"


class PostmarkIntegration(TimeStampedModel):
    singleton_key = models.CharField(
        max_length=20,
        unique=True,
        default="default",
        editable=False,
    )
    server_api_token_encrypted = models.TextField(blank=True, editable=False)
    from_email = models.EmailField(
        blank=True,
        help_text="A sender signature or domain verified in this client's Postmark server.",
    )
    recipient_emails = models.TextField(
        blank=True,
        max_length=4000,
        help_text="One form-submission recipient email address per line.",
    )
    message_stream = models.CharField(
        max_length=100,
        default="outbound",
        help_text="The Postmark message stream used for contact-form notifications.",
    )
    is_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Enable Postmark delivery only after the client has a Postmark server, "
            "a verified sender, recipients, and a Server API token."
        ),
    )

    class Meta:
        verbose_name = "Postmark integration"
        verbose_name_plural = "Postmark integration"

    @property
    def normalized_recipient_emails(self):
        return [
            email.strip()
            for email in self.recipient_emails.replace(",", "\n").splitlines()
            if email.strip()
        ]

    @property
    def server_api_token_configured(self):
        return bool(self.get_server_api_token())

    def set_server_api_token(self, token):
        value = token.strip()
        self.server_api_token_encrypted = (
            _postmark_cipher().encrypt(value.encode()).decode() if value else ""
        )

    def get_server_api_token(self):
        if not self.server_api_token_encrypted:
            return ""
        try:
            return (
                _postmark_cipher()
                .decrypt(self.server_api_token_encrypted.encode())
                .decode()
            )
        except (InvalidToken, ValueError, TypeError, UnicodeDecodeError):
            return ""

    def clean(self):
        if self.pk is None and PostmarkIntegration.objects.exists():
            raise ValidationError("Only one Postmark integration is allowed.")

        invalid_recipients = []
        for email in self.normalized_recipient_emails:
            try:
                validate_email(email)
            except ValidationError:
                invalid_recipients.append(email)
        if invalid_recipients:
            raise ValidationError(
                {"recipient_emails": "Enter valid recipient email addresses only."}
            )
        if len(self.normalized_recipient_emails) > 20:
            raise ValidationError(
                {"recipient_emails": "Enter no more than 20 recipient addresses."}
            )

    def __str__(self):
        return "Postmark integration"


class GoogleServicesIntegration(TimeStampedModel):
    singleton_key = models.CharField(
        max_length=20,
        unique=True,
        default="default",
        editable=False,
    )
    connected_email = models.EmailField(blank=True)
    refresh_token_encrypted = models.TextField(blank=True, editable=False)
    authorized_scopes = models.TextField(blank=True, editable=False)
    analytics_account_id = models.CharField(max_length=120, blank=True)
    analytics_property_id = models.CharField(max_length=120, blank=True)
    analytics_data_stream_id = models.CharField(max_length=120, blank=True)
    analytics_measurement_id = models.CharField(
        max_length=50,
        blank=True,
        validators=[
            RegexValidator(
                r"^$|^G-[A-Za-z0-9]+$",
                "Enter a valid GA4 measurement ID.",
            )
        ],
    )
    search_console_property_url = models.URLField(blank=True)
    search_console_verification_token = models.CharField(
        max_length=255,
        blank=True,
    )
    connected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Google Analytics and Search Console"
        verbose_name_plural = "Google Analytics and Search Console"

    @property
    def refresh_token_configured(self):
        return bool(self.refresh_token_encrypted)

    def clean(self):
        if self.pk is None and GoogleServicesIntegration.objects.exists():
            raise ValidationError(
                "Only one Google services integration is allowed."
            )

    def __str__(self):
        return self.connected_email or "Google Analytics and Search Console"


class AnthemCRMIntegration(TimeStampedModel):
    singleton_key = models.CharField(
        max_length=20,
        unique=True,
        default="default",
        editable=False,
    )
    webhook_url_encrypted = models.TextField(blank=True, editable=False)
    is_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Enable delivery only after the client-specific Anthem CRM webhook "
            "has been entered and a controlled form test is ready."
        ),
    )

    class Meta:
        verbose_name = "Anthem CRM integration"
        verbose_name_plural = "Anthem CRM integration"

    @property
    def webhook_url_configured(self):
        return bool(self.get_webhook_url())

    def set_webhook_url(self, webhook_url):
        value = webhook_url.strip()
        if value:
            validate_anthem_webhook_url(value)
        self.webhook_url_encrypted = (
            _anthem_cipher().encrypt(value.encode()).decode() if value else ""
        )

    def get_webhook_url(self):
        if not self.webhook_url_encrypted:
            return ""
        try:
            return (
                _anthem_cipher()
                .decrypt(self.webhook_url_encrypted.encode())
                .decode()
            )
        except (InvalidToken, ValueError, TypeError, UnicodeDecodeError):
            return ""

    def clean(self):
        if self.pk is None and AnthemCRMIntegration.objects.exists():
            raise ValidationError("Only one Anthem CRM integration is allowed.")
        webhook_url = self.get_webhook_url()
        if webhook_url:
            validate_anthem_webhook_url(webhook_url)

    def __str__(self):
        return "Anthem CRM integration"


class PublishableModel(TimeStampedModel):
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    summary = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    open_graph_title = models.CharField(max_length=70, blank=True)
    open_graph_description = models.CharField(max_length=200, blank=True)
    open_graph_image = models.FileField(
        upload_to="open-graph/%Y/%m/",
        blank=True,
    )
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

    @property
    def resolved_open_graph_title(self):
        return self.open_graph_title or self.seo_title

    @property
    def resolved_open_graph_description(self):
        return self.open_graph_description or self.seo_description

    @property
    def word_count(self):
        return len(strip_tags(self.body).split())

    def _populate_metadata_defaults(self):
        plain_body = " ".join(strip_tags(self.body).split())
        description_source = self.summary or plain_body
        if not self.meta_title:
            self.meta_title = Truncator(self.title).chars(70)
        if not self.meta_description and description_source:
            self.meta_description = Truncator(description_source).chars(160)
        if not self.open_graph_title:
            self.open_graph_title = self.meta_title
        if not self.open_graph_description and description_source:
            self.open_graph_description = Truncator(description_source).chars(200)

    def clean(self):
        super().clean()
        self._populate_metadata_defaults()
        if self.is_published and not 650 <= self.word_count <= 900:
            raise ValidationError(
                {
                    "body": (
                        "Published content pages should be approximately 750 words. "
                        f"This page currently has {self.word_count} words; use 650–900."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self._populate_metadata_defaults()
        return super().save(*args, **kwargs)

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


class FAQ(TimeStampedModel):
    question = models.CharField(max_length=240)
    answer = models.TextField()
    is_published = models.BooleanField(default=False, db_index=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "question"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class Lead(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        CLOSED = "closed", "Closed"

    class AnthemDeliveryStatus(models.TextChoices):
        NOT_SENT = "not_sent", "Not sent"
        ATTEMPTING = "attempting", "Attempting"
        CONFIRMED = "confirmed", "Confirmed"
        NEEDS_REVIEW = "needs_review", "Needs review"
        CONFIGURATION_ERROR = "configuration_error", "Configuration error"

    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    message = models.TextField(max_length=10000)
    source = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    consent_to_contact = models.BooleanField(default=False)
    anthem_delivery_status = models.CharField(
        max_length=32,
        choices=AnthemDeliveryStatus.choices,
        default=AnthemDeliveryStatus.NOT_SENT,
    )
    anthem_attempted_at = models.DateTimeField(null=True, blank=True)
    anthem_http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    anthem_error_summary = models.CharField(max_length=240, blank=True)
    anthem_record_identifier = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class DownloadableAsset(TimeStampedModel):
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="downloads/%Y/%m/")
    is_published = models.BooleanField(default=False)

    def __str__(self):
        return self.title
