from django.conf import settings
from django.db import migrations


def _user_model(apps):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    return apps.get_model(app_label, model_name)


def seed_defaults(apps, schema_editor):
    TreasuryAccount = apps.get_model("core", "TreasuryAccount")
    SiteAppearance = apps.get_model("core", "SiteAppearance")
    UserProfile = apps.get_model("core", "UserProfile")
    User = _user_model(apps)

    for kind, label in [
        ("internal", "الخزنة الداخلية"),
        ("external", "الخزنة الخارجية"),
    ]:
        TreasuryAccount.objects.get_or_create(
            kind=kind,
            defaults={"label": label, "is_active": True},
        )
    SiteAppearance.objects.get_or_create(pk=1)

    for u in User.objects.all():
        role = "super_admin" if getattr(u, "is_superuser", False) else "user"
        UserProfile.objects.get_or_create(user=u, defaults={"role": role})


def unseed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_step1_db_design"),
    ]

    operations = [
        migrations.RunPython(seed_defaults, unseed),
    ]
