from django.db import migrations


def seed(apps, schema_editor):
    Slide = apps.get_model('travel', 'HomeSlide')
    slides = [
        ('Find your calm in a winter wonderland.', 'Alpine escapes', 'Snow-covered forests, cosy retreats and a little room to breathe.', 'lake-v2.webp'),
        ('Where blue skies meet timeless beauty.', 'Greece · Island stories', 'Discover sunlit lanes and unforgettable Aegean views.', 'greece-v2.webp'),
        ('Take the scenic route to extraordinary.', 'Alpine countryside · Scenic journeys', 'Rolling meadows, mountain villages and views worth slowing down for.', 'switzerland-v2.webp'),
        ('Let the backwaters set your pace.', 'Kerala · Backwater moments', "Palm-lined waterways and peaceful days in God's Own Country.", 'kerala-v2.webp'),
        ('Chase the sunset. Keep the memories.', 'Tropical escapes', 'Golden evenings and beautiful places, planned around you.', 'sunset-v2.jpg'),
    ]
    for i, (title, eyebrow, caption, image) in enumerate(slides):
        Slide.objects.using(schema_editor.connection.alias).get_or_create(order=i, defaults={'title': title, 'eyebrow': eyebrow, 'caption': caption, 'built_in_image': 'img/hero/' + image})


class Migration(migrations.Migration):
    dependencies = [('travel', '0006_audio_requested_controls')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
