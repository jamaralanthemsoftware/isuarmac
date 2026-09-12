from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_postmarkintegration"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lead",
            name="message",
            field=models.TextField(max_length=10000),
        ),
    ]