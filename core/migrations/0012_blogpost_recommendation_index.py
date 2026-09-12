from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_blog_importer"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="blogpost",
            index=models.Index(
                fields=[
                    "is_published",
                    "-original_published_at",
                    "-created_at",
                ],
                name="blogpost_pub_recent_idx",
            ),
        ),
    ]