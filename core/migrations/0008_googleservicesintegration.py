import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_limit_lead_message_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="GoogleServicesIntegration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "singleton_key",
                    models.CharField(
                        default="default",
                        editable=False,
                        max_length=20,
                        unique=True,
                    ),
                ),
                ("connected_email", models.EmailField(blank=True, max_length=254)),
                (
                    "refresh_token_encrypted",
                    models.TextField(blank=True, editable=False),
                ),
                (
                    "authorized_scopes",
                    models.TextField(blank=True, editable=False),
                ),
                (
                    "analytics_account_id",
                    models.CharField(blank=True, max_length=120),
                ),
                (
                    "analytics_property_id",
                    models.CharField(blank=True, max_length=120),
                ),
                (
                    "analytics_data_stream_id",
                    models.CharField(blank=True, max_length=120),
                ),
                (
                    "analytics_measurement_id",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^$|^G-[A-Za-z0-9]+$",
                                "Enter a valid GA4 measurement ID.",
                            )
                        ],
                    ),
                ),
                (
                    "search_console_property_url",
                    models.URLField(blank=True),
                ),
                (
                    "search_console_verification_token",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "connected_at",
                    models.DateTimeField(blank=True, null=True),
                ),
            ],
            options={
                "verbose_name": "Google Analytics and Search Console",
                "verbose_name_plural": "Google Analytics and Search Console",
            },
        ),
    ]