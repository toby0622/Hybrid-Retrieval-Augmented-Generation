import json
import re
from typing import Any, Dict, Optional


def serialize_neo4j_value(value):
    if value is None:
        return None

    type_name = type(value).__module__ + "." + type(value).__name__
    if "neo4j.time" in type_name:
        if hasattr(value, "iso_format"):
            return value.iso_format()
        elif hasattr(value, "to_native"):
            return str(value.to_native())
        else:
            return str(value)

    if isinstance(value, list):
        return [serialize_neo4j_value(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize_neo4j_value(v) for k, v in value.items()}

    return value


def serialize_neo4j_properties(props: dict) -> dict:
    return {k: serialize_neo4j_value(v) for k, v in props.items()}


# ─────────── Cypher Sanitization ───────────

_CYPHER_DESTRUCTIVE_PATTERN = re.compile(
    r"\b(DELETE|DETACH\s+DELETE|REMOVE|DROP|CREATE\s+INDEX|DROP\s+INDEX|"
    r"CREATE\s+CONSTRAINT|DROP\s+CONSTRAINT|SET\s+|CALL\s+dbms\.|CALL\s+apoc\.)"
    r"(?!\s*\()",  # allow SET inside RETURN aliases
    re.IGNORECASE,
)


def sanitize_cypher(cypher: str) -> str:
    """
    Remove destructive operations from LLM-generated Cypher queries.
    Returns the sanitized query, or raises ValueError if the whole query
    is destructive.
    """
    if not cypher or not cypher.strip():
        return ""

    # Strip markdown fences
    cypher = cypher.replace("```cypher", "").replace("```", "").strip()

    # Check for destructive operations
    if _CYPHER_DESTRUCTIVE_PATTERN.search(cypher):
        raise ValueError(
            f"Cypher query contains destructive operations and was blocked: "
            f"{cypher[:100]}..."
        )

    return cypher


_NEO4J_LABEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_neo4j_label(label: str) -> str:
    """
    Validate that a Neo4j label name is safe (alphanumeric + underscores).
    Raises ValueError if the label contains dangerous characters.
    """
    if not label or not _NEO4J_LABEL_PATTERN.match(label):
        raise ValueError(
            f"Invalid Neo4j label: '{label}'. "
            f"Labels must start with a letter/underscore and contain only "
            f"alphanumeric characters and underscores."
        )
    return label


# ─────────── LLM JSON Parsing ───────────


def parse_llm_json(
    content: str, prefix: str = "{", fallback_regex: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Parse JSON from LLM output, handling common issues:
    - Missing opening brace/bracket
    - Markdown code fences
    - Smart quotes
    - Unbalanced braces

    Args:
        content: Raw LLM output string
        prefix: Expected prefix character ("{" for objects, "[" for arrays)
        fallback_regex: Whether to attempt regex extraction on JSON parse failure

    Returns:
        Parsed JSON value, or None if parsing fails entirely
    """
    if not content:
        return None

    content = content.strip()

    # Normalize smart quotes
    content = content.replace("\u201c", '"').replace("\u201d", '"')

    # Ensure starts with expected prefix
    if not content.startswith(prefix):
        content = prefix + content

    # Extract from markdown code fences
    if "```" in content:
        parts = content.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                content = stripped[4:].strip()
                break
            elif stripped.startswith(prefix):
                content = stripped
                break

    # Balance braces
    open_char = prefix
    close_char = "}" if prefix == "{" else "]"
    balance = content.count(open_char) - content.count(close_char)
    if balance > 0:
        content = content + close_char * balance

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        if fallback_regex and prefix == "{":
            # Attempt regex extraction for key-value pairs
            pattern = r'"(\w+)":\s*"([^"]+)"'
            matches = re.findall(pattern, content)
            if matches:
                return {
                    k: v for k, v in matches if v.lower() != "null"
                }
        return None
