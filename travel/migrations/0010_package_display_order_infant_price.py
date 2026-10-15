from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("travel", "0009_validate_quotes_reviews"),
    ]

    operations = [
        migrations.AddField(
            model_name="package",
            name="display_order",
            field=models.PositiveIntegerField(default=100, help_text="Lower numbers appear first in package lists"),
        ),
        migrations.AddField(
            model_name="package",
            name="infant_price",
            field=models.PositiveIntegerField(default=0, help_text="Infant price per person (reference only; confirmed by travel team)"),
        ),
        migrations.AlterModelOptions(
            name="package",
            options={"ordering": ["display_order", "-is_featured", "-created"]},
        ),
    ]
