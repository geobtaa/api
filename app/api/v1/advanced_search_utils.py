"""
Utilities for advanced multi-field search functionality.
"""

from typing import List, Optional

from fastapi import HTTPException

# Valid boolean operators
VALID_OPERATORS = {"AND", "OR", "NOT"}


def validate_advanced_query_clause(clause: dict) -> dict:
    """Validate and normalize a single advanced query clause.

    Args:
        clause: Query clause dict with keys: operator, field, query

    Returns:
        Normalized clause dict with ES field name

    Raises:
        HTTPException: If clause is invalid
    """
    if not isinstance(clause, dict):
        raise HTTPException(
            status_code=400,
            detail=(
                "Each advanced query clause must be a dictionary with "
                "'operator', 'field', and 'query' keys"
            ),
        )

    operator = clause.get("operator")
    field = clause.get("field")
    query = clause.get("query")

    # Validate operator
    if not operator:
        raise HTTPException(
            status_code=400,
            detail="Missing 'operator' in advanced query clause. Must be one of: AND, OR, NOT",
        )

    operator_upper = operator.upper()
    if operator_upper not in VALID_OPERATORS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid operator '{operator}'. Must be one of: {', '.join(VALID_OPERATORS)}",
        )

    # Validate field - must be a non-empty string (Elasticsearch will validate the field exists)
    if not field:
        raise HTTPException(status_code=400, detail="Missing 'field' in advanced query clause")

    if not isinstance(field, str) or not field.strip():
        raise HTTPException(
            status_code=400,
            detail="'field' must be a non-empty string containing the Elasticsearch field name",
        )

    # Validate query
    if not query or not isinstance(query, str) or not query.strip():
        raise HTTPException(
            status_code=400, detail="Missing or empty 'query' in advanced query clause"
        )

    return {"operator": operator_upper, "field": field.strip(), "query": query.strip()}


def validate_advanced_queries(advanced_queries: Optional[List[dict]]) -> Optional[List[dict]]:
    """Validate and normalize advanced queries list.

    Args:
        advanced_queries: List of query clause dicts

    Returns:
        List of normalized query clause dicts

    Raises:
        HTTPException: If queries are invalid
    """
    if advanced_queries is None:
        return None

    if not isinstance(advanced_queries, list):
        raise HTTPException(
            status_code=400, detail="'advanced_queries' must be a list of query clause objects"
        )

    if len(advanced_queries) == 0:
        raise HTTPException(status_code=400, detail="'advanced_queries' cannot be an empty list")

    validated_queries = []
    for i, clause in enumerate(advanced_queries):
        try:
            validated_clause = validate_advanced_query_clause(clause)
            validated_queries.append(validated_clause)
        except HTTPException as e:
            raise HTTPException(
                status_code=e.status_code, detail=f"Error in advanced_queries[{i}]: {e.detail}"
            ) from e

    return validated_queries
