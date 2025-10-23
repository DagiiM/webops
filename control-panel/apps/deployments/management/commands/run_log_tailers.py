"""
Django management command to run robust log tailers for LLM deployments.

Usage examples:
    python manage.py run_log_tailers --deployment my-llm
    python manage.py run_log_tailers --all-llm
    python manage.py run_log_tailers --deployment-id 42 \
        --rate 10 --burst 20 --chunk-lines 200 --chunk-bytes 65536 --flush-interval 0.5

Features:
- Tails vLLM stdout/stderr files (systemd append targets) with rotation handling.
- Chunked aggregation, backpressure, and token-bucket rate limiting.
- Streams chunks to Channels group `deployment_{name}` using `deployment_logs` events.
- Zero external dependencies beyond Django/Channels already in the project.

"""

from __future__ import annotations

import asyncio
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.deployments.models import BaseDeployment, ApplicationDeployment
from apps.deployments.services.llm import LLMDeploymentService
from apps.deployments.shared.log_tailer import run_tailers_for_deployment


class Command(BaseCommand):
    help = "Run log tailers for LLM deployments and stream to Channels groups"

    def add_arguments(self, parser) -> None:
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--deployment",
            dest="deployment_name",
            type=str,
            help="Deployment name to tail",
        )
        group.add_argument(
            "--deployment-id",
            dest="deployment_id",
            type=int,
            help="Deployment ID to tail",
        )
        group.add_argument(
            "--all-llm",
            dest="all_llm",
            action="store_true",
            help="Tail logs for all LLM deployments",
        )

        # Tailer configuration
        parser.add_argument("--rate", dest="rate", type=float, default=10.0, help="Chunks per second")
        parser.add_argument("--burst", dest="burst", type=int, default=20, help="Burst size in chunks")
        parser.add_argument("--chunk-lines", dest="chunk_lines", type=int, default=200, help="Max lines per chunk")
        parser.add_argument(
            "--chunk-bytes",
            dest="chunk_bytes",
            type=int,
            default=64 * 1024,
            help="Max bytes per chunk",
        )
        parser.add_argument(
            "--flush-interval",
            dest="flush_interval",
            type=float,
            default=0.5,
            help="Flush interval in seconds",
        )
        parser.add_argument(
            "--queue-size",
            dest="queue_size",
            type=int,
            default=1000,
            help="Max queued lines before backpressure",
        )

    def handle(self, *args, **options) -> None:
        # Resolve target deployments
        deployments: list[ApplicationDeployment] = []

        if options.get("all_llm"):
            deployments = list(ApplicationDeployment.objects.filter(project_type=ApplicationDeployment.ProjectType.LLM))
            if not deployments:
                raise CommandError("No LLM deployments found")
        elif options.get("deployment_id") is not None:
            dep_id = options["deployment_id"]
            try:
                deployment = ApplicationDeployment.objects.get(id=dep_id, project_type=ApplicationDeployment.ProjectType.LLM)
            except ApplicationDeployment.DoesNotExist:
                raise CommandError(f"LLM deployment with id={dep_id} not found")
            deployments = [deployment]
        elif options.get("deployment_name"):
            name = options["deployment_name"]
            try:
                deployment = ApplicationDeployment.objects.get(name=name, project_type=ApplicationDeployment.ProjectType.LLM)
            except ApplicationDeployment.DoesNotExist:
                raise CommandError(f"LLM deployment '{name}' not found")
            deployments = [deployment]
        else:
            # Should not happen due to mutually exclusive group required
            raise CommandError("Specify --deployment, --deployment-id, or --all-llm")

        # Tailer config
        rate = float(options.get("rate", 10.0))
        burst = int(options.get("burst", 20))
        chunk_lines = int(options.get("chunk_lines", 200))
        chunk_bytes = int(options.get("chunk_bytes", 64 * 1024))
        flush_interval = float(options.get("flush_interval", 0.5))
        queue_size = int(options.get("queue_size", 1000))

        # Build tasks for selected deployments
        llm_service = LLMDeploymentService()

        async def run_all() -> None:
            tasks = []
            for dep in deployments:
                base_path = str(llm_service.get_deployment_path(dep))
                # Ensure logs directory exists; vLLM service writes here
                # Do not create files; only directory to avoid permission errors
                try:
                    import os
                    os.makedirs(os.path.join(base_path, "logs"), exist_ok=True)
                except Exception:
                    # Best-effort; continue regardless
                    pass

                tasks.append(
                    run_tailers_for_deployment(
                        deployment_id=dep.id,
                        deployment_name=dep.name,
                        deployment_path=base_path,
                        queue_maxsize=queue_size,
                        chunk_max_lines=chunk_lines,
                        chunk_max_bytes=chunk_bytes,
                        flush_interval=flush_interval,
                        max_line_bytes=16 * 1024,
                        rate_chunks_per_sec=rate,
                        rate_burst=burst,
                    )
                )

            # Run tailers concurrently; keep running until cancelled
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                pass

        # Run event loop for tailers
        asyncio.run(run_all())