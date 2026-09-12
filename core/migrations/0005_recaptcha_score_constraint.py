from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_recaptchaintegration"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="recaptchaintegration",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("minimum_score__gte", Decimal("0")),
                    ("minimum_score__lte", Decimal("1")),
                ),
                name="recaptcha_minimum_score_between_zero_and_one",
            ),
        ),
    ]