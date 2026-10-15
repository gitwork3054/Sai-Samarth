from django.db import migrations, models


def seed_default_link(apps, schema_editor):
    Link = apps.get_model("travel", "InternationalGroupLink")
    Link.objects.get_or_create(
        name="All International Group Tours",
        defaults={
            "url": "https://www.flamingotravels.co.in/international-tour-packages",
            "order": 0,
            "is_active": True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("travel", "0010_package_display_order_infant_price"),
    ]

    operations = [
        migrations.CreateModel(
            name="InternationalGroupLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(help_text="Country, region or collection name shown on International Group Tours", max_length=120)),
                ("url", models.URLField(help_text="Flamingo Travels page opened directly when the visitor clicks this card")),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "International group tour link",
                "verbose_name_plural": "International group tour links",
                "ordering": ["order", "name"],
            },
        ),
        migrations.RunPython(seed_default_link, migrations.RunPython.noop),
    ]
