from dataclasses import dataclass, field
from typing import Dict, List, Optional

SCHEMA_NAME = "DevOps Incident Management"
SCHEMA_DESCRIPTION = (
    "Schema for DevOps infrastructure: services, incidents, metrics, and logs"
)


@dataclass
class Entity:
    name: str
    description: str
    properties: Dict[str, str] = field(default_factory=dict)
    extraction_hints: List[str] = field(default_factory=list)


@dataclass
class Relation:
    source: str
    target: str
    name: str
    description: str = ""
    properties: List[str] = field(default_factory=list)


@dataclass
class DevOpsSchema:
    entities: Dict[str, Entity]
    relations: List[Relation]


ENTITY_SCHEMAS = {
    "Service": Entity(
        name="Service",
        description="A microservice or system component in the infrastructure",
        properties={
            "name": "Service name (e.g., auth-service, payment-api)",
            "version": "Current deployed version",
            "language": "Programming language (Go, Python, Java, Node.js)",
            "owner": "Team owning the service",
            "tier": "Service tier (tier1-critical, tier2-important, tier3-normal)",
            "health_status": "Current health (healthy, degraded, unhealthy)",
            "last_deploy": "Last deployment timestamp",
        },
        extraction_hints=[
            "Look for service names in error messages",
            "Check for microservice naming patterns like xxx-service, xxx-api",
            "Common services: auth, user, payment, notification, gateway",
        ],
    ),
    "Incident": Entity(
        name="Incident",
        description="A production incident or outage event requiring investigation",
        properties={
            "id": "Unique incident identifier (e.g., INC-2024-001)",
            "title": "Short summary of the incident",
            "description": "Detailed description of the incident",
            "severity": "Severity level (SEV1, SEV2, SEV3, SEV4, SEV5)",
            "status": "Current status (Open, Investigating, Mitigated, Resolved)",
            "created_at": "Incident creation timestamp",
            "resolved_at": "Incident resolution timestamp (if resolved)",
            "root_cause": "Identified root cause",
            "impact": "Business impact description",
        },
        extraction_hints=[
            "Look for severity indicators like SEV1, P0, critical",
            "Check for incident IDs starting with INC-, ALERT-",
            "Status keywords: investigating, mitigating, resolved",
        ],
    ),
    "Metric": Entity(
        name="Metric",
        description="Time-series data point or anomaly indicator",
        properties={
            "name": "Metric name (e.g., cpu_usage, memory_percent, request_latency_p99)",
            "value": "Observed metric value",
            "unit": "Measurement unit (percent, ms, count, bytes)",
            "timestamp": "Time of measurement",
            "threshold": "Alert threshold value",
            "anomaly_score": "Anomaly detection score (0-1)",
        },
        extraction_hints=[
            "Look for metric patterns like xxx_usage, xxx_latency",
            "Check for numerical values with units",
            "Common metrics: CPU, memory, latency, error rate, throughput",
        ],
    ),
    "Log": Entity(
        name="Log",
        description="System log entry from a service",
        properties={
            "level": "Log level (DEBUG, INFO, WARN, ERROR, FATAL)",
            "message": "Log message content",
            "timestamp": "Log timestamp",
            "trace_id": "Distributed trace ID for correlation",
            "span_id": "Span ID within the trace",
            "source_file": "Source file that generated the log",
            "line_number": "Line number in source file",
        },
        extraction_hints=[
            "Look for log levels like ERROR, WARN, FATAL",
            "Check for trace IDs (usually UUID format)",
            "Error messages often contain stack traces",
        ],
    ),
    "Team": Entity(
        name="Team",
        description="Engineering team responsible for services",
        properties={
            "name": "Team name (e.g., platform-team, payments-team)",
            "slack_channel": "Team's Slack channel for alerts",
            "oncall": "Current on-call engineer",
        },
        extraction_hints=[
            "Look for team names in ownership metadata",
            "Check for @mentions in incident discussions",
        ],
    ),
    "Deployment": Entity(
        name="Deployment",
        description="A deployment event for a service",
        properties={
            "id": "Deployment ID",
            "version": "Deployed version",
            "timestamp": "Deployment timestamp",
            "environment": "Target environment (production, staging, dev)",
            "status": "Deployment status (success, failed, rolled_back)",
            "commit_sha": "Git commit SHA",
        },
        extraction_hints=[
            "Look for deployment patterns",
            "Check for version changes before incidents",
        ],
    ),
}

RELATION_SCHEMAS = [
    Relation(
        source="Service",
        target="Service",
        name="DEPENDS_ON",
        description="Service dependency - source service calls target service",
        properties=["protocol", "latency_budget_ms"],
    ),
    Relation(
        source="Incident",
        target="Service",
        name="AFFECTS",
        description="Incident impacts the specified service",
        properties=["impact_level"],
    ),
    Relation(
        source="Log",
        target="Service",
        name="GENERATED_BY",
        description="Log entry was produced by the specified service",
    ),
    Relation(
        source="Metric",
        target="Service",
        name="MEASURES",
        description="Metric monitors the specified service's performance",
    ),
    Relation(
        source="Incident",
        target="Metric",
        name="TRIGGERED_BY",
        description="Metric anomaly triggered the incident alert",
    ),
    Relation(
        source="Service",
        target="Team",
        name="OWNED_BY",
        description="Service is owned and maintained by the team",
    ),
    Relation(
        source="Deployment",
        target="Service",
        name="DEPLOYED_TO",
        description="Deployment was applied to the service",
    ),
    Relation(
        source="Incident",
        target="Deployment",
        name="CAUSED_BY",
        description="Incident was caused by a deployment",
    ),
    Relation(
        source="Log",
        target="Incident",
        name="RELATED_TO",
        description="Log entry is related to an incident investigation",
    ),
]


def get_schema_for_llm_prompt() -> str:
    lines = []
    lines.append("# Neo4j Graph Schema for DevOps Domain\n")

    lines.append("## Node Labels and Properties\n")
    for entity_name, entity in ENTITY_SCHEMAS.items():
        lines.append(f"### {entity_name}")
        lines.append(f"Description: {entity.description}")
        lines.append("Properties:")
        for prop, desc in entity.properties.items():
            lines.append(f"  - {prop}: {desc}")
        lines.append("")

    lines.append("## Relationship Types\n")
    for rel in RELATION_SCHEMAS:
        lines.append(f"### (:{rel.source})-[:{rel.name}]->(:{rel.target})")
        lines.append(f"Description: {rel.description}")
        if rel.properties:
            lines.append(f"Properties: {', '.join(rel.properties)}")
        lines.append("")

    lines.append("## Example Cypher Queries\n")
    lines.append("```cypher")
    lines.append("-- Find service and its dependencies")
    lines.append(
        "MATCH (s:Service {name: 'auth-service'})-[:DEPENDS_ON]->(dep:Service)"
    )
    lines.append("RETURN s.name, collect(dep.name) as dependencies")
    lines.append("")
    lines.append("-- Find incidents affecting a service")
    lines.append("MATCH (inc:Incident)-[:AFFECTS]->(s:Service)")
    lines.append("WHERE toLower(s.name) CONTAINS toLower('payment')")
    lines.append("RETURN inc.title, inc.severity, s.name")
    lines.append("")
    lines.append("-- Find error logs for a service")
    lines.append("MATCH (log:Log)-[:GENERATED_BY]->(s:Service)")
    lines.append("WHERE log.level = 'ERROR' AND s.name = 'auth-service'")
    lines.append("RETURN log.message, log.timestamp")
    lines.append("ORDER BY log.timestamp DESC LIMIT 10")
    lines.append("```")

    return "\n".join(lines)
