from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import TrashSettings


@receiver(post_migrate)
def create_default_trash_settings(sender, **kwargs):
    """
    Create default trash settings after migration
    """
    if sender.name == 'apps.trash':
        TrashSettings.objects.get_or_create(pk=1)
