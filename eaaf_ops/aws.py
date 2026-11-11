"""Collect ECS evidence using read-only AWS CLI operations."""

import json
import re
import subprocess

from .incident import normalize_export, objects


def aws_json(operation, arguments, *, region=None, profile=None):
    command = ["aws", "ecs", operation, *arguments, "--output", "json", "--no-cli-pager"]
    if region:
        command.extend(["--region", region])
    if profile:
        command.extend(["--profile", profile])
    try:
        result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", timeout=45)
    except FileNotFoundError as error:
        raise ValueError("Install AWS CLI v2 to collect ECS evidence.") from error
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"AWS ECS {operation} timed out.") from error
    if result.returncode:
        code = re.search(r"An error occurred \(([A-Za-z0-9]+)\)", result.stderr)
        detail = f" ({code[1]})" if code else ""
        raise ValueError(f"AWS ECS {operation} failed{detail}. Check your CLI session and permissions.")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"AWS ECS {operation} returned invalid JSON.") from error


def collect_incident(cluster, service, *, region=None, profile=None):
    context = {"region": region, "profile": profile}
    services = aws_json("describe-services", ["--cluster", cluster, "--services", service], **context)
    incident = normalize_export(services, service)

    listing = aws_json("list-tasks", [
        "--cluster", cluster, "--service-name", service,
        "--desired-status", "STOPPED", "--max-items", "10",
    ], **context)
    arns = listing.get("taskArns") if isinstance(listing, dict) else None
    if not isinstance(arns, list) or any(not isinstance(arn, str) or not arn.startswith("arn:") for arn in arns):
        raise ValueError("AWS ECS list-tasks returned invalid task ARNs.")
    if arns:
        tasks = aws_json("describe-tasks", ["--cluster", cluster, "--tasks", *arns], **context)
        incident = normalize_export(services, service, tasks)
        failures = objects(tasks, "failures") if "failures" in tasks else []
        if failures:
            incident["collection_notes"] = [
                f"ECS could not describe {len(failures)} listed task(s).",
            ]
    if listing.get("NextToken"):
        incident.setdefault("collection_notes", []).append("Stopped task collection was limited to 10 tasks.")
    return incident
