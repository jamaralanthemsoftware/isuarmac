from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_blogpost_recommendation_index"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlogPostRelatedSelection",
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
                (
                    "position",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "1"), (2, "2"), (3, "3")],
                        help_text="The order in which this article appears.",
                    ),
                ),
                (
                    "related_post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="selected_as_related",
                        to="core.blogpost",
                    ),
                ),
                (
                    "source_post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="related_selections",
                        to="core.blogpost",
                    ),
                ),
            ],
            options={
                "verbose_name": "important related article",
                "verbose_name_plural": "important related articles",
                "ordering": ["position"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("source_post", "related_post"),
                        name="blogpost_related_unique_post",
                    ),
                    models.UniqueConstraint(
                        fields=("source_post", "position"),
                        name="blogpost_related_unique_position",
                    ),
                    models.CheckConstraint(
                        condition=~models.Q(
                            source_post=models.F("related_post")
                        ),
                        name="blogpost_related_not_self",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            position__gte=1,
                            position__lte=3,
                        ),
                        name="blogpost_related_position_1_to_3",
                    ),
                ],
            },
        ),
    ]