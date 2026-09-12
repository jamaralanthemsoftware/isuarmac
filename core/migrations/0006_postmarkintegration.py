from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_recaptcha_score_constraint"),
    ]

    operations = [
        migrations.CreateModel(
            name="PostmarkIntegration",
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
                    "server_api_token_encrypted",
                    models.TextField(blank=True, editable=False),
                ),
                (
                    "from_email",
                    models.EmailField(
                        blank=True,
                        help_text=(
                            "A sender signature or domain verified in this "
                            "client's Postmark server."
                        ),
                        max_length=254,
                    ),
                ),
                (
                    "recipient_emails",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "One form-submission recipient email address per line."
                        ),
                        max_length=4000,
                    ),
                ),
                (
                    "message_stream",
                    models.CharField(
                        default="outbound",
                        help_text=(
                            "The Postmark message stream used for "
                            "contact-form notifications."
                        ),
                        max_length=100,
                    ),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Enable Postmark delivery only after the client has "
                            "a Postmark server, a verified sender, recipients, "
                            "and a Server API token."
                        ),
                    ),
                ),
            ],
            options={
                "verbose_name": "Postmark integration",
                "verbose_name_plural": "Postmark integration",
            },
        ),
    ]