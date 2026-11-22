"""webops deploy: one bounded, auditable GitHub deployment command.

AI may assess deployment risks but cannot create workloads, execute its own
suggested shell commands, or bypass the operator approval and WebOps RBAC.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import click

from .deployment_flow import (
    DeploymentPlan, DeploymentPreflightError, read_only_jani_review,
    safe_checkout, wait_for_deployment, verify_worktree_matches_plan,
)


@click.command("deploy")
@click.argument("repository", required=False)
@click.option("--repo", "repo_option", default="", help="GitHub owner/repo or HTTPS URL")
@click.option("--name", default="", help="Application name; defaults to repo name")
@click.option("--branch", default="main", show_default=True)
@click.option("--domain", default="", help="Optional deployment domain")
@click.option("--ai-assist", is_flag=True, help="Require a read-only Jani deployment review")
@click.option("--model", default="", help="Hosted model name (or WEBOPS_MODEL)")
@click.option("--model-endpoint", default="", help="OpenAI-compatible /v1 URL")
@click.option("--model-key-env", default="WEBOPS_MODEL_API_KEY", show_default=True,
              help="Name of an environment variable containing the model access key")
@click.option("--jani-binary", default="jani", help="Path to installed Jani executable")
@click.option("--worktree", type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Existing cloned checkout; otherwise fetch from GitHub")
@click.option("--approve", is_flag=True, help="Explicit approval to submit deployment")
@click.option("--dry-run", is_flag=True, help="Validate and review, but do not submit")
@click.option("--wait", is_flag=True, help="Wait for WebOps to report running")
@click.option("--timeout", type=click.IntRange(1, 600), default=180, show_default=True)
@click.option("--json-output", is_flag=True, help="Print machine-readable result")
def one_deploy(repository, repo_option, name, branch, domain, ai_assist, model,
               model_endpoint, model_key_env, jani_binary, worktree, approve,
               dry_run, wait, timeout, json_output):
    """Deploy a GitHub project in one command, optionally reviewed by Jani.

    Example: webops deploy ifinsta/ifinsta --ai-assist --model qwen3:1.7b
             --model-endpoint http://127.0.0.1:8001/v1 --approve --wait

    The model is advisory only; the WebOps authenticated API executes deployment.
    """
    try:
        if bool(repository) == bool(repo_option):
            raise DeploymentPreflightError("Provide one repository argument or --repo")
        plan = DeploymentPlan.from_input(repository or repo_option, name, branch, domain)
        record = {"spec": plan.display(), "mode": "dry_run" if dry_run else "deploy"}
        key = os.environ.get(model_key_env, "")
        endpoint = model_endpoint or os.environ.get("WEBOPS_MODEL_ENDPOINT", "")
        selected_model = model or os.environ.get("WEBOPS_MODEL", "")
        if ai_assist:
            if not endpoint or not selected_model or not key:
                raise DeploymentPreflightError(
                    "AI review requires model, endpoint and model key environment variable"
                )
            if worktree:
                verify_worktree_matches_plan(plan, worktree)
                evidence = read_only_jani_review(
                    plan, worktree, selected_model, endpoint, key, jani_binary,
                    min(timeout, 600))
            else:
                with tempfile.TemporaryDirectory(prefix="webops-ai-deploy-") as temp:
                    checkout = Path(temp) / "source"
                    safe_checkout(plan, checkout, os.environ.get("GITHUB_TOKEN", ""))
                    evidence = read_only_jani_review(
                        plan, checkout, selected_model, endpoint, key, jani_binary,
                        min(timeout, 600))
            record["ai_review"] = {
                "agent": "jani", "model": evidence.model,
                "sha256": evidence.digest, "duration_ms": evidence.duration_ms,
                "read_only": True,
            }
            # The text is shown but never treated as commands or API settings.
            if not json_output:
                click.echo("Jani read-only risk review:\n" + evidence.output_preview)
        if dry_run:
            record["status"] = "validated"
            click.echo(json.dumps(record, sort_keys=True) if json_output
                       else "Plan validated (nothing deployed): " + json.dumps(record["spec"]))
            return
        if not approve:
            if not click.confirm("Submit this reviewed specification to WebOps?", default=False):
                raise DeploymentPreflightError("Deployment not approved")
        # Delay credentials until after input validation, read-only review, and approval.
        from .cli import get_api_client
        client = get_api_client()
        try:
            outcome = client.create_deployment(
                name=plan.name, repo_url=plan.repo_url,
                branch=plan.branch, domain=plan.domain
            )
            record["id"] = outcome.get("id")
            record["status"] = "submitted"
            if wait:
                state = wait_for_deployment(
                    lambda: client.get_deployment(plan.name), timeout=timeout
                )
                record["status"] = str(state.get("status", "running"))
                record["provider_reported_running"] = True
                record["http_health_verified"] = False
        finally:
            client.close()
        click.echo(json.dumps(record, sort_keys=True) if json_output
                   else f"WebOps deployment {plan.name}: {record['status']}"
                        " (use webops info and logs to verify service health)")
    except DeploymentPreflightError as exc:
        raise click.ClickException(str(exc)) from exc

