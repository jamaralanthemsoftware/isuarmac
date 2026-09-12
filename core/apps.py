from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Website"

    def ready(self):
        from . import checks  # noqa: F401
        from . import security  # noqa: F401
