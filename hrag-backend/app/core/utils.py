def serialize_neo4j_value(value):
    """Convert Neo4j special types to JSON-serializable formats."""
    if value is None:
        return None
    
    # Handle Neo4j DateTime types
    type_name = type(value).__module__ + '.' + type(value).__name__
    if 'neo4j.time' in type_name:
        # Convert neo4j.time.DateTime, Date, Time, Duration to ISO string
        if hasattr(value, 'iso_format'):
            return value.iso_format()
        elif hasattr(value, 'to_native'):
            return str(value.to_native())
        else:
            return str(value)
    
    # Handle lists and dicts recursively
    if isinstance(value, list):
        return [serialize_neo4j_value(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize_neo4j_value(v) for k, v in value.items()}
    
    return value


def serialize_neo4j_properties(props: dict) -> dict:
    """Serialize all properties from a Neo4j node."""
    return {k: serialize_neo4j_value(v) for k, v in props.items()}
