import json
from pathlib import Path

import pytest

from eaaf_ops.__main__ import diagnose


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
