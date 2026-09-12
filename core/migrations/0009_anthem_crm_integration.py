from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_googleservicesintegration"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnthemCRMIntegration",
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
                    "webhook_url_encrypted",
                    models.TextField(blank=True, editable=False),
                ),
                (
                    "is_enabled",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Enable delivery only after the client-specific "
                            "Anthem CRM webhook has been entered and a controlled "
                            "form test is ready."
                        ),
                    ),
                ),
            ],
            options={
                "verbose_name": "Anthem CRM integration",
                "verbose_name_plural": "Anthem CRM integration",
            },
        ),
        migrations.AddField(
            model_name="lead",
            name="anthem_delivery_status",
            field=models.CharField(
                choices=[
                    ("not_sent", "Not sent"),
                    ("attempting", "Attempting"),
                    ("confirmed", "Confirmed"),
                    ("needs_review", "Needs review"),
                    ("configuration_error", "Configuration error"),
                ],
                default="not_sent",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="anthem_attempted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lead",
            name="anthem_http_status",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lead",
            name="anthem_error_summary",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="lead",
            name="anthem_record_identifier",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]