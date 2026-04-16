from django.db import migrations

def create_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='administrator')
    Group.objects.get_or_create(name='operator')

def delete_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['administrator', 'operator']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_mensajero'),  # ajusta al nombre de tu última migración
    ]

    operations = [
        migrations.RunPython(create_groups, delete_groups),
    ]