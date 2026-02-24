# DevOps Incident Response Skill

This skill enables HRAG to function as a DevOps incident response copilot.

## Capabilities

- **Incident Triage** — Classify and prioritize incoming incidents
- **Root Cause Analysis** — Correlate data from knowledge graph and vector search
- **Service Dependency Mapping** — Understand how services relate to each other
- **Remediation Guidance** — Provide actionable fix recommendations

## Supported Intents

| Intent | Description |
|--------|-------------|
| `question` | General informational queries about services or architecture |
| `troubleshoot` | Active incident investigation and debugging |
| `status` | Service health and status checks |
| `chat` | General conversation |
| `end` | End the current session |

## Slot Requirements

- **service_name** (required) — The affected service or component
- **error_type** (optional) — The type of error observed
- **time_range** (optional) — When the issue occurred
- **severity** (optional) — Incident severity level

## Usage

This skill is automatically loaded when the HRAG system starts. It can be
activated via the API or by setting `ACTIVE_SKILL=devops_incident` in `.env`.
