from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = "Creates the 'administrator' and 'operator' permission groups"

    def handle(self, *args, **kwargs):
        for name in ["administrator", "operator"]:
            group, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Group "{name}" created successfully.'))
            else:
                self.stdout.write(f'Group "{name}" already exists, skipping.')