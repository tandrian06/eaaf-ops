import json
from pathlib import Path
from subprocess import CompletedProcess

from eaaf_ops import aws
from eaaf_ops.__main__ import main


def test_live_cli_collects_read_only_evidence(monkeypatch, capsys):
    services = json.loads(Path("examples/ecs-describe-services.json").read_text())
    tasks = json.loads(Path("examples/ecs-describe-tasks.json").read_text())
    arn = tasks["tasks"][0]["taskArn"]
    payloads = {
        "describe-services": services,
        "list-tasks": {"taskArns": [arn]},
        "describe-tasks": tasks,
    }
    calls = []

    def run(command, **kwargs):
        assert command[:2] == ["aws", "ecs"]
        assert command[-4:] == ["--region", "eu-north-1", "--profile", "sandbox"]
        calls.append(command)
        return CompletedProcess(command, 0, json.dumps(payloads[command[2]]), "")

    monkeypatch.setattr(aws.subprocess, "run", run)
    monkeypatch.setattr("sys.argv", [
        "eaaf_ops", "--aws-cluster", "example", "--service", "example-web",
        "--region", "eu-north-1", "--profile", "sandbox",
    ])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["finding"] == "container_out_of_memory"
    assert [command[2] for command in calls] == ["describe-services", "list-tasks", "describe-tasks"]
    assert calls[1][3:11] == [
        "--cluster", "example", "--service-name", "example-web",
        "--desired-status", "STOPPED", "--max-items", "10",
    ]
    assert calls[2][6] == arn


def test_live_collection_skips_describe_without_stopped_tasks(monkeypatch):
    services = json.loads(Path("examples/ecs-describe-services.json").read_text())

    def aws_json(operation, arguments, **context):
        return {"describe-services": services, "list-tasks": {"taskArns": []}}[operation]

    monkeypatch.setattr(aws, "aws_json", aws_json)
    incident = aws.collect_incident("example", "example-web")
    assert incident["events"] == services["services"][0]["events"]
