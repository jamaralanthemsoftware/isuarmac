import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

DEFAULT_SUPERUSER_USERNAME = "jamaral@anthemsoftware.com"
DEFAULT_SUPERUSER_EMAIL = "jamaral@anthemsoftware.com"


class Command(BaseCommand):
    help = "Create the initial superuser from DJANGO_SUPERUSER_* environment variables."

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", DEFAULT_SUPERUSER_USERNAME)
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", DEFAULT_SUPERUSER_EMAIL)
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        if not password:
            raise CommandError("Set DJANGO_SUPERUSER_PASSWORD as a secure environment secret.")

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created superuser {username}."))
        else:
            self.stdout.write(f"Superuser {username} already exists; no changes made.")
