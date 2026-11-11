"""Normalize ECS exports and identify explicit failure signals."""

import re


def objects(payload, field):
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object.")
    items = payload.get(field)
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError(f"Expected a list of objects in {field}.")
    return items


def normalize_export(payload, service_name=None, task_export=None):
    services = objects(payload, "services")
    if service_name:
        services = [service for service in services if service.get("serviceName") == service_name]
    if len(services) != 1:
        raise ValueError("Provide one ECS service or select it explicitly with --service.")
    service = services[0]
    name = service.get("serviceName")
    cluster = service.get("clusterArn")
    events = objects(service, "events").copy()
    if task_export is not None:
        if not isinstance(cluster, str) or not cluster:
            raise ValueError("The service export needs clusterArn to associate stopped tasks.")
        for task in objects(task_export, "tasks"):
            if task.get("lastStatus") != "STOPPED":
                continue
            if task.get("clusterArn") != cluster or task.get("group") != f"service:{name}":
                raise ValueError("A stopped task belongs to another cluster or service.")
            arn = task.get("taskArn")
            if not isinstance(arn, str) or not arn.rsplit("/", 1)[-1]:
                raise ValueError("A stopped task is missing its taskArn.")
            task_id = arn.rsplit("/", 1)[-1]
            stopped_at = task.get("stoppedAt")
            if task.get("stoppedReason"):
                events.append({
                    "id": f"task:{task_id}", "message": task["stoppedReason"], "createdAt": stopped_at,
                })
            containers = objects(task, "containers") if "containers" in task else []
            for index, container in enumerate(containers):
                if container.get("reason"):
                    events.append({
                        "id": f"task:{task_id}:container:{index}",
                        "message": container["reason"],
                        "createdAt": stopped_at,
                    })
    return {"service": name, "events": events}


SIGNALS = {
    "container_image_not_found": (
        re.compile(r"CannotPullContainerError[\s\S]*(?:not found|manifest unknown)", re.I),
        "ECS could not start the task because the registry could not resolve the configured container image.",
        "Compare the image URI and tag in the ECS task definition with a manifest in the registry.",
    ),
    "container_out_of_memory": (
        re.compile(r"\bOutOfMemoryError\b", re.I),
        "ECS reported that a container exceeded its available memory.",
        "Compare the container and task memory limits with memory usage around the stopped task.",
    ),
}


def diagnose(incident):
    if not isinstance(incident, dict) or not isinstance(incident.get("service"), str) or not incident["service"].strip():
        raise ValueError("Expected a nonempty service name.")
    events = objects(incident, "events")
    evidence = {name: [] for name in SIGNALS}
    seen = set()
    for event in events:
        event_id = event.get("id")
        message = event.get("message")
        if not isinstance(event_id, str) or not event_id.strip() or event_id in seen:
            raise ValueError("Each event needs a unique, nonempty ID.")
        if not isinstance(message, str) or not message.strip() or len(message) > 2000:
            raise ValueError("Each event needs a message of up to 2,000 characters.")
        seen.add(event_id)
        for name, (pattern, _, _) in SIGNALS.items():
            if pattern.search(message):
                item = {"id": event_id, "message": message}
                timestamp = event.get("createdAt")
                if isinstance(timestamp, (str, int, float)) and timestamp:
                    item["timestamp"] = timestamp
                evidence[name].append(item)

    findings = [
        {"finding": name, "probable_cause": cause, "evidence": evidence[name], "next_check": check}
        for name, (_, cause, check) in SIGNALS.items()
        if evidence[name]
    ]
    report = {"service": incident["service"]}
    if len(findings) == 1:
        return {**report, **findings[0]}
    if findings:
        return {
            **report,
            "finding": "multiple_failure_signals",
            "probable_cause": None,
            "evidence": [],
            "next_check": "Correlate the signals with task stop times and deployment revisions.",
            "observed_failures": findings,
        }
    return {
        **report,
        "finding": "insufficient_evidence",
        "probable_cause": None,
        "evidence": [],
        "next_check": "Collect the ECS service events and the stopped task reason for the incident window.",
    }
