from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class Entity:
    name: str
    description: str
    properties: Dict[str, str] = field(default_factory=dict)

@dataclass
class Relation:
    source: str
    target: str
    name: str
    description: str = ""

@dataclass
class DevOpsSchema:
    entities: Dict[str, Entity]
    relations: List[Relation]

ENTITY_SCHEMAS = {
    "Incident": Entity(
        name="Incident",
        description="A production incident or outage event",
        properties={
            "id": "Unique identifier",
            "description": "Summary of the incident",
            "severity": "SEV1 to SEV5",
            "status": "Open, Resolved, Investigating",
            "created_at": "Timestamp",
        }
    ),
    "Service": Entity(
        name="Service",
        description="A microservice or system component",
        properties={
            "name": "Service name",
            "version": "Deploy version",
            "language": "Programming language (Go, Python, Java)",
            "owner": "Team owning the service",
        }
    ),
    "Metric": Entity(
        name="Metric",
        description="Time-series data point or anomaly",
        properties={
            "name": "Metric name (e.g., cpu_usage)",
            "value": "Observed value",
            "timestamp": "Time required",
        }
    ),
    "Log": Entity(
        name="Log",
        description="System log entry",
        properties={
            "level": "INFO, WARN, ERROR",
            "message": "Log content",
            "trace_id": "Distributed trace ID",
        }
    )
}

RELATION_SCHEMAS = [
    Relation("Incident", "Service", "AFFECTS", "Incident impacts a specific service"),
    Relation("Service", "Service", "DEPENDS_ON", "Service call dependency"),
    Relation("Log", "Service", "GENERATED_BY", "Log belongs to a service"),
    Relation("Metric", "Service", "MEASURES", "Metric tracks service performance"),
    Relation("Incident", "Metric", "TRIGGERED_BY", "Metric anomaly caused incident"),
]
