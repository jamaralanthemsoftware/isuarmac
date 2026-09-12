from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_page_open_graph_description_page_open_graph_image_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecaptchaIntegration",
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
                (
                    "site_key",
                    models.CharField(
                        blank=True,
                        help_text="The public Google reCAPTCHA v3 site key.",
                        max_length=255,
                    ),
                ),
                (
                    "secret_key_encrypted",
                    models.TextField(blank=True, editable=False),
                ),
                (
                    "minimum_score",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.80"),
                        help_text=(
                            "Reject scores below this value. "
                            "The template default is 0.80."
                        ),
                        max_digits=3,
                    ),
                ),
                (
                    "allowed_hostnames",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "One permanent hostname per line, "
                            "without https:// or a path."
                        ),
                    ),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Enable reCAPTCHA v3 on the public contact form only "
                            "after the permanent domain, site key, secret key, and "
                            "allowed hostnames are configured."
                        ),
                    ),
                ),
            ],
            options={
                "verbose_name": "reCAPTCHA integration",
                "verbose_name_plural": "reCAPTCHA integration",
            },
        ),
    ]