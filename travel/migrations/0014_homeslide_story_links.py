from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("travel", "0013_savedinternationaltrip"),
    ]

    operations = [
        migrations.AddField(
            model_name="homeslide",
            name="link_url",
            field=models.CharField(
                blank=True,
                max_length=300,
                help_text="Optional destination link for the immersive journey chapter (e.g. /domestic/ or /international/).",
            ),
        ),
        migrations.AddField(
            model_name="homeslide",
            name="link_text",
            field=models.CharField(
                blank=True,
                default="Explore this escape",
                max_length=70,
                help_text="Text of the chapter action button.",
            ),
        ),
    ]
