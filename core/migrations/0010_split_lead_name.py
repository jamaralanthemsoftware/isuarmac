from django.db import migrations, models


def split_existing_names(apps, schema_editor):
    Lead = apps.get_model("core", "Lead")
    for lead in Lead.objects.all().iterator():
        parts = lead.name.strip().split(maxsplit=1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""
        Lead.objects.filter(pk=lead.pk).update(
            first_name=first_name[:60],
            last_name=last_name[:60],
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_anthem_crm_integration"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="first_name",
            field=models.CharField(max_length=60, null=True),
        ),
        migrations.AddField(
            model_name="lead",
            name="last_name",
            field=models.CharField(max_length=60, null=True),
        ),
        migrations.RunPython(
            split_existing_names,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="lead",
            name="first_name",
            field=models.CharField(max_length=60),
        ),
        migrations.AlterField(
            model_name="lead",
            name="last_name",
            field=models.CharField(max_length=60),
        ),
        migrations.RemoveField(
            model_name="lead",
            name="name",
        ),
    ]