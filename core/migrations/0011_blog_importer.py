from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_split_lead_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BlogPost",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=240)),
                ("slug", models.SlugField(max_length=240)),
                ("summary", models.CharField(blank=True, max_length=500)),
                ("body", models.TextField(blank=True)),
                ("meta_title", models.CharField(blank=True, max_length=70)),
                ("meta_description", models.CharField(blank=True, max_length=300)),
                ("canonical_url", models.URLField(blank=True, max_length=1000)),
                ("source_url", models.URLField(blank=True, max_length=1000)),
                ("source_guid", models.CharField(blank=True, max_length=1000)),
                ("author_name", models.CharField(blank=True, max_length=255)),
                ("original_published_at", models.DateTimeField(blank=True, null=True)),
                ("original_modified_at", models.DateTimeField(blank=True, null=True)),
                ("featured_image", models.FileField(blank=True, upload_to="blog-posts/%Y/%m/")),
                ("is_published", models.BooleanField(db_index=True, default=False)),
            ],
            options={"ordering": ["-original_published_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="BlogImportRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("mode", models.CharField(choices=[("wxr", "WordPress WXR upload"), ("sitemap", "Public sitemap URL")], max_length=20)),
                ("source_url", models.URLField(blank=True, max_length=1000)),
                ("uploaded_name", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(choices=[("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="running", max_length=20)),
                ("imported_count", models.PositiveIntegerField(default=0)),
                ("duplicate_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("error_summary", models.TextField(blank=True)),
                ("limits", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="blog_import_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="BlogImportItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_url", models.URLField(blank=True, max_length=1000)),
                ("source_guid", models.CharField(blank=True, max_length=1000)),
                ("title", models.CharField(blank=True, max_length=240)),
                ("status", models.CharField(choices=[("imported", "Imported"), ("duplicate", "Duplicate"), ("failed", "Failed")], max_length=20)),
                ("error_summary", models.TextField(blank=True)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("blog_post", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="import_items", to="core.blogpost")),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="core.blogimportrun")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddConstraint(
            model_name="blogpost",
            constraint=models.UniqueConstraint(condition=~models.Q(("source_url", "")), fields=("source_url",), name="blogpost_unique_source_url"),
        ),
        migrations.AddConstraint(
            model_name="blogpost",
            constraint=models.UniqueConstraint(condition=~models.Q(("source_guid", "")), fields=("source_guid",), name="blogpost_unique_source_guid"),
        ),
    ]