"""
Enron Email Dataset Ontology Schema

This module defines the ontology for entity and relation extraction from the Enron email dataset.
It provides structured guidance for LLM-based knowledge graph construction, ensuring consistent
entity/relation types across all emails.

Design Principles:
1. Explicit entity/relation definitions prevent ad-hoc schema creation
2. Modular design allows easy adaptation to different datasets
3. JSON-serializable for LLM prompt injection
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# =============================================================================
# Entity Definitions
# =============================================================================


class EntityType(str, Enum):
    """Entity types for the email knowledge graph."""

    PERSON = "Person"
    EMAIL = "Email"
    ORGANIZATION = "Organization"
    TOPIC = "Topic"
    PROJECT = "Project"
    MEETING = "Meeting"
    DOCUMENT = "Document"


@dataclass
class EntitySchema:
    """Schema definition for an entity type."""

    name: str
    description: str
    properties: List[str]
    extraction_hints: List[str] = field(default_factory=list)


# Entity definitions with extraction guidance
ENTITY_SCHEMAS: Dict[EntityType, EntitySchema] = {
    EntityType.PERSON: EntitySchema(
        name="Person",
        description="An individual mentioned in emails as sender, recipient, or referenced person",
        properties=["name", "email", "department", "role", "phone"],
        extraction_hints=[
            "Extract from From, To, Cc, X-From, X-To fields",
            "Look for names in email signatures",
            "Identify people mentioned by name in email body",
            "Common patterns: 'firstname.lastname@enron.com'",
        ],
    ),
    EntityType.EMAIL: EntitySchema(
        name="Email",
        description="An individual email message",
        properties=[
            "message_id",
            "subject",
            "date",
            "folder",
            "content_preview",
            "has_attachment",
        ],
        extraction_hints=[
            "Use Message-ID as unique identifier",
            "Parse Date field for timestamp",
            "X-Folder indicates the mailbox location",
        ],
    ),
    EntityType.ORGANIZATION: EntitySchema(
        name="Organization",
        description="A company, department, or organizational unit",
        properties=["name", "type", "industry"],
        extraction_hints=[
            "Enron Corp is the primary organization",
            "Look for department names: 'Enron Trading', 'Enron Gas', etc.",
            "External companies mentioned in business discussions",
            "Government agencies: FERC, SEC, California PUC, etc.",
        ],
    ),
    EntityType.TOPIC: EntitySchema(
        name="Topic",
        description="A subject matter or theme discussed in emails",
        properties=["name", "category"],
        extraction_hints=[
            "Energy trading, California energy crisis",
            "Financial matters, accounting practices",
            "Legal issues, regulatory compliance",
            "General business topics from Subject lines",
        ],
    ),
    EntityType.PROJECT: EntitySchema(
        name="Project",
        description="A business project, deal, or initiative",
        properties=["name", "status", "department", "value"],
        extraction_hints=[
            "Look for deal names, project codenames",
            "Pipeline projects, trading positions",
            "Merger/acquisition discussions",
        ],
    ),
    EntityType.MEETING: EntitySchema(
        name="Meeting",
        description="A scheduled meeting or event",
        properties=["title", "date", "time", "location", "attendees"],
        extraction_hints=[
            "Calendar invitations in email body",
            "References to scheduled calls or meetings",
            "Conference room bookings",
        ],
    ),
    EntityType.DOCUMENT: EntitySchema(
        name="Document",
        description="A file or document referenced or attached",
        properties=["filename", "type", "description"],
        extraction_hints=[
            "Look for '<< File: filename.ext >>' patterns",
            "References to spreadsheets, presentations",
            "Contract and legal document references",
        ],
    ),
}


# =============================================================================
# Relation Definitions
# =============================================================================


class RelationType(str, Enum):
    """Relation types for the email knowledge graph."""

    # Email-Person relations
    SENT_BY = "SENT_BY"
    SENT_TO = "SENT_TO"
    CC_TO = "CC_TO"
    BCC_TO = "BCC_TO"
    MENTIONS_PERSON = "MENTIONS_PERSON"

    # Email-Organization relations
    MENTIONS_ORG = "MENTIONS_ORG"

    # Email-Topic relations
    DISCUSSES_TOPIC = "DISCUSSES_TOPIC"

    # Email-Project relations
    RELATES_TO_PROJECT = "RELATES_TO_PROJECT"

    # Email-Meeting relations
    SCHEDULES_MEETING = "SCHEDULES_MEETING"

    # Email-Document relations
    HAS_ATTACHMENT = "HAS_ATTACHMENT"
    REFERENCES_DOCUMENT = "REFERENCES_DOCUMENT"

    # Email-Email relations
    REPLIES_TO = "REPLIES_TO"
    FORWARDS = "FORWARDS"
    THREAD_PART_OF = "THREAD_PART_OF"

    # Person-Organization relations
    WORKS_AT = "WORKS_AT"
    MANAGES = "MANAGES"
    REPORTS_TO = "REPORTS_TO"

    # Person-Person relations
    COMMUNICATES_WITH = "COMMUNICATES_WITH"


@dataclass
class RelationSchema:
    """Schema definition for a relation type."""

    name: str
    from_entity: EntityType
    to_entity: EntityType
    description: str
    properties: List[str] = field(default_factory=list)
    extraction_hints: List[str] = field(default_factory=list)


# Relation definitions with extraction guidance
RELATION_SCHEMAS: Dict[RelationType, RelationSchema] = {
    # Email-Person relations
    RelationType.SENT_BY: RelationSchema(
        name="SENT_BY",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.PERSON,
        description="The person who sent the email",
        properties=["timestamp"],
        extraction_hints=["Extract from 'From' header field"],
    ),
    RelationType.SENT_TO: RelationSchema(
        name="SENT_TO",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.PERSON,
        description="Direct recipient of the email",
        properties=["timestamp"],
        extraction_hints=["Extract from 'To' header field", "May have multiple recipients"],
    ),
    RelationType.CC_TO: RelationSchema(
        name="CC_TO",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.PERSON,
        description="CC recipient of the email",
        properties=["timestamp"],
        extraction_hints=["Extract from 'X-cc' header field"],
    ),
    RelationType.BCC_TO: RelationSchema(
        name="BCC_TO",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.PERSON,
        description="BCC recipient of the email",
        properties=["timestamp"],
        extraction_hints=["Extract from 'X-bcc' header field"],
    ),
    RelationType.MENTIONS_PERSON: RelationSchema(
        name="MENTIONS_PERSON",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.PERSON,
        description="A person mentioned in the email body",
        properties=["context"],
        extraction_hints=[
            "Look for names in email body text",
            "Exclude sender and recipients already captured",
        ],
    ),
    # Email-Organization relations
    RelationType.MENTIONS_ORG: RelationSchema(
        name="MENTIONS_ORG",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.ORGANIZATION,
        description="An organization mentioned in the email",
        properties=["context"],
        extraction_hints=["Company names, department names", "Government agencies"],
    ),
    # Email-Topic relations
    RelationType.DISCUSSES_TOPIC: RelationSchema(
        name="DISCUSSES_TOPIC",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.TOPIC,
        description="A topic or subject discussed in the email",
        properties=["relevance_score"],
        extraction_hints=["Infer from subject line and body content"],
    ),
    # Email-Project relations
    RelationType.RELATES_TO_PROJECT: RelationSchema(
        name="RELATES_TO_PROJECT",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.PROJECT,
        description="A project or deal discussed in the email",
        properties=["context"],
        extraction_hints=["Look for project names, deal references"],
    ),
    # Email-Meeting relations
    RelationType.SCHEDULES_MEETING: RelationSchema(
        name="SCHEDULES_MEETING",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.MEETING,
        description="A meeting scheduled or referenced in the email",
        properties=["context"],
        extraction_hints=["Calendar entries, meeting invitations"],
    ),
    # Email-Document relations
    RelationType.HAS_ATTACHMENT: RelationSchema(
        name="HAS_ATTACHMENT",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.DOCUMENT,
        description="A file attached to the email",
        properties=[],
        extraction_hints=["Look for '<< File: ... >>' patterns"],
    ),
    RelationType.REFERENCES_DOCUMENT: RelationSchema(
        name="REFERENCES_DOCUMENT",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.DOCUMENT,
        description="A document referenced but not attached",
        properties=["context"],
        extraction_hints=["References to external documents, 'see attached' phrases"],
    ),
    # Email-Email relations
    RelationType.REPLIES_TO: RelationSchema(
        name="REPLIES_TO",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.EMAIL,
        description="This email is a reply to another email",
        properties=[],
        extraction_hints=[
            "Look for 'RE:' in subject",
            "'-----Original Message-----' in body",
        ],
    ),
    RelationType.FORWARDS: RelationSchema(
        name="FORWARDS",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.EMAIL,
        description="This email forwards another email",
        properties=[],
        extraction_hints=["Look for 'FW:' or 'FWD:' in subject"],
    ),
    RelationType.THREAD_PART_OF: RelationSchema(
        name="THREAD_PART_OF",
        from_entity=EntityType.EMAIL,
        to_entity=EntityType.EMAIL,
        description="Email is part of a conversation thread",
        properties=["thread_position"],
        extraction_hints=["Group by normalized subject line"],
    ),
    # Person-Organization relations
    RelationType.WORKS_AT: RelationSchema(
        name="WORKS_AT",
        from_entity=EntityType.PERSON,
        to_entity=EntityType.ORGANIZATION,
        description="Person is employed at organization",
        properties=["department", "role", "start_date"],
        extraction_hints=["Infer from email domain", "Job titles in signatures"],
    ),
    RelationType.MANAGES: RelationSchema(
        name="MANAGES",
        from_entity=EntityType.PERSON,
        to_entity=EntityType.PERSON,
        description="Person manages another person",
        properties=[],
        extraction_hints=["Infer from organizational hierarchy cues"],
    ),
    RelationType.REPORTS_TO: RelationSchema(
        name="REPORTS_TO",
        from_entity=EntityType.PERSON,
        to_entity=EntityType.PERSON,
        description="Person reports to another person",
        properties=[],
        extraction_hints=["Infer from organizational hierarchy cues"],
    ),
    # Person-Person relations
    RelationType.COMMUNICATES_WITH: RelationSchema(
        name="COMMUNICATES_WITH",
        from_entity=EntityType.PERSON,
        to_entity=EntityType.PERSON,
        description="Two people communicate via email",
        properties=["email_count", "first_contact", "last_contact"],
        extraction_hints=["Aggregate from email sender/recipient pairs"],
    ),
}


# =============================================================================
# Schema Export Functions
# =============================================================================


def get_entity_types() -> List[str]:
    """Get list of all entity type names."""
    return [e.value for e in EntityType]


def get_relation_types() -> List[str]:
    """Get list of all relation type names."""
    return [r.value for r in RelationType]


def get_schema_for_llm_prompt() -> str:
    """
    Generate a formatted schema description for LLM prompts.
    This helps guide the LLM to extract consistent entities and relations.
    """
    lines = [
        "# Email Knowledge Graph Schema",
        "",
        "## Entity Types",
        "",
    ]

    for entity_type, schema in ENTITY_SCHEMAS.items():
        lines.append(f"### {schema.name}")
        lines.append(f"Description: {schema.description}")
        lines.append(f"Properties: {', '.join(schema.properties)}")
        if schema.extraction_hints:
            lines.append("Extraction hints:")
            for hint in schema.extraction_hints:
                lines.append(f"  - {hint}")
        lines.append("")

    lines.append("## Relation Types")
    lines.append("")

    for relation_type, schema in RELATION_SCHEMAS.items():
        lines.append(f"### {schema.name}")
        lines.append(
            f"({schema.from_entity.value}) -[{schema.name}]-> ({schema.to_entity.value})"
        )
        lines.append(f"Description: {schema.description}")
        if schema.properties:
            lines.append(f"Properties: {', '.join(schema.properties)}")
        if schema.extraction_hints:
            lines.append("Extraction hints:")
            for hint in schema.extraction_hints:
                lines.append(f"  - {hint}")
        lines.append("")

    return "\n".join(lines)


def get_schema_as_dict() -> dict:
    """
    Export schema as a dictionary for JSON serialization.
    Useful for API responses or configuration files.
    """
    return {
        "entities": {
            entity_type.value: {
                "name": schema.name,
                "description": schema.description,
                "properties": schema.properties,
                "extraction_hints": schema.extraction_hints,
            }
            for entity_type, schema in ENTITY_SCHEMAS.items()
        },
        "relations": {
            relation_type.value: {
                "name": schema.name,
                "from_entity": schema.from_entity.value,
                "to_entity": schema.to_entity.value,
                "description": schema.description,
                "properties": schema.properties,
                "extraction_hints": schema.extraction_hints,
            }
            for relation_type, schema in RELATION_SCHEMAS.items()
        },
    }


# =============================================================================
# Core Entity/Relation Lists for Database Initialization
# =============================================================================

# These are the primary relations to create during initial data loading
# More complex relations (MENTIONS_*, DISCUSSES_*) require LLM extraction
PRIMARY_RELATIONS = [
    RelationType.SENT_BY,
    RelationType.SENT_TO,
    RelationType.CC_TO,
    RelationType.BCC_TO,
    RelationType.HAS_ATTACHMENT,
    RelationType.REPLIES_TO,
    RelationType.FORWARDS,
    RelationType.WORKS_AT,
]

# These relations require LLM-based extraction from email content
LLM_EXTRACTED_RELATIONS = [
    RelationType.MENTIONS_PERSON,
    RelationType.MENTIONS_ORG,
    RelationType.DISCUSSES_TOPIC,
    RelationType.RELATES_TO_PROJECT,
    RelationType.SCHEDULES_MEETING,
    RelationType.REFERENCES_DOCUMENT,
    RelationType.COMMUNICATES_WITH,
]


if __name__ == "__main__":
    # Demo: print schema for LLM prompt
    print(get_schema_for_llm_prompt())
