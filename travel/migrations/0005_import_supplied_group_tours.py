from django.db import migrations
from travel.group_import import import_catalogue


def import_groups(apps, schema_editor):
    import_catalogue(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [('travel', '0004_imported_group_tour_fields')]
    operations = [migrations.RunPython(import_groups, migrations.RunPython.noop)]
