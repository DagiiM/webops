"""Run the safety review on requests that are waiting for an operator and have no report yet."""
from django.core.management.base import BaseCommand

from apps.core.common.utils.validators import parse_github_repo
from apps.deployments.models import ApplicationDeployment
from apps.deployments.services.ai_assist import AssistError
from apps.deployments.services.safety_review import ReviewError
from apps.deployments.views.application_deployment import _safety_review


class Command(BaseCommand):
    help = "Backfill the safety review for requests that predate it."

    def handle(self, *args, **options):
        pending = ApplicationDeployment.objects.filter(status="requested", is_deleted=False)
        count = 0
        for d in pending:
            if d.safety_report:
                continue
            parsed = parse_github_repo(d.repo_url)
            if not parsed:
                self.stdout.write(f"{d.name}: not a GitHub repository, skipped")
                continue
            try:
                report = _safety_review(d.deployed_by, parsed, d.branch, d.static_only)
            except (ReviewError, AssistError) as exc:
                self.stdout.write(f"{d.name}: review could not run ({exc})")
                continue
            if report:
                d.safety_report = report
                d.save(update_fields=["safety_report"])
                count += 1
                self.stdout.write(f"{d.name}: {report['decision']} ({len(report['findings'])} findings)")
        self.stdout.write(f"{count} request(s) reviewed.")
