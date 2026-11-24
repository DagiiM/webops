from django.core.management.base import BaseCommand
from apps.services.background.worker import run_worker

class Command(BaseCommand):
    help="Run the exclusive SQLite background worker under a process supervisor."
    def handle(self,*args,**options):
        run_worker()
