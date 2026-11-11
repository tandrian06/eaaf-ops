import json
from pathlib import Path

import pytest

from eaaf_ops.__main__ import main
from eaaf_ops.incident import diagnose, normalize_export


def test_image_missing_uses_only_matching_event():
    incident = json.loads(Path("examples/ecs-image-not-found.json").read_text())
    report = diagnose(incident)
    assert report["finding"] == "container_image_not_found"
    assert [event["id"] for event in report["evidence"]] == ["event-2"]


def test_other_pull_error_remains_unclassified():
    report = diagnose({"service": "example", "events": [
        {"id": "event-1", "message": "CannotPullContainerError: connection timed out"},
    ]})
    assert report["finding"] == "insufficient_evidence"
    assert report["probable_cause"] is None


def test_duplicate_evidence_ids_are_rejected():
    event = {"id": "event-1", "message": "ECS started a task."}
    with pytest.raises(ValueError, match="unique"):
        diagnose({"service": "example", "events": [event, event]})


def test_aws_exports_detect_explicit_memory_failure(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", [
        "eaaf_ops", "examples/ecs-describe-services.json",
        "--tasks", "examples/ecs-describe-tasks.json",
    ])
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["finding"] == "container_out_of_memory"
    assert report["evidence"][0]["id"].endswith(":container:0")


def test_stopped_task_must_belong_to_selected_service():
    service = json.loads(Path("examples/ecs-describe-services.json").read_text())
    tasks = json.loads(Path("examples/ecs-describe-tasks.json").read_text())
    tasks["tasks"][0]["clusterArn"] = "another-cluster"
    with pytest.raises(ValueError, match="another cluster or service"):
        normalize_export(service, task_export=tasks)


def test_multiple_signals_do_not_claim_one_root_cause():
    report = diagnose({"service": "example", "events": [
        {"id": "pull", "message": "CannotPullContainerError: manifest unknown"},
        {"id": "memory", "message": "OutOfMemoryError: container stopped"},
    ]})
    assert report["finding"] == "multiple_failure_signals"
    assert report["probable_cause"] is None
    assert [item["evidence"][0]["id"] for item in report["observed_failures"]] == ["pull", "memory"]


def test_exit_137_alone_does_not_imply_out_of_memory():
    service = json.loads(Path("examples/ecs-describe-services.json").read_text())
    tasks = json.loads(Path("examples/ecs-describe-tasks.json").read_text())
    del tasks["tasks"][0]["containers"][0]["reason"]
    assert diagnose(normalize_export(service, task_export=tasks))["finding"] == "insufficient_evidence"
