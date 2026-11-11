# EAAF AI for Ops

Replay an ECS incident from a captured event file. The CLI reports a probable cause, supporting event IDs and messages, and the next check. The first increment recognizes the image-not-found failure observed in the EAAF deployment demo. The example replaces the real infrastructure identifiers with fictional values.

## Try it locally

From this repository with Python 3.14:

```powershell
python -m eaaf_ops examples/ecs-image-not-found.json
```

The expected finding is `container_image_not_found`, supported by `event-2`. An unsupported event set produces `insufficient_evidence`. Use a snapshot from one incident window. A captured failure does not establish the current service health.

## Request an explanation through EAAF Core

Start [EAAF Core](https://github.com/tandrian06/eaaf) locally. Set `EAAF_OPS_API_KEY` in your shell to an application key from the Core configuration authorized for the requested alias. For this increment, the existing IT policy can be used locally with `eaaf-mock-it`. The CLI reads the environment variable and sends the request to the local Gateway. `EAAF_GATEWAY_URL` overrides the default `http://127.0.0.1:8000`.

```powershell
python -m eaaf_ops examples/ecs-image-not-found.json --model eaaf-mock-it
```

The mock verifies routing and returns a fixed message. The finding and its evidence come from the local rule. With an enabled and authorized real model, the optional completion explains the same report. Use sanitized inputs with external providers. Keep keys in local configuration outside Git.

The CLI only reads the event file and optionally calls the Gateway. It has no AWS credentials, AWS API calls, or remediation actions.
