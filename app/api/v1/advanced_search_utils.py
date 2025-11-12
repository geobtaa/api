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
        clause: Query clause dict with keys: op, f, q

    Returns:
        Normalized clause dict with ES field name

    Raises:
        HTTPException: If clause is invalid
    """
    if not isinstance(clause, dict):
        raise HTTPException(
            status_code=400,
            detail=("Each advanced query clause must be a dictionary with 'op', 'f', and 'q' keys"),
        )

    operator = clause.get("op")
    field = clause.get("f")
    query = clause.get("q")

    # Validate operator
    if not operator:
        raise HTTPException(
            status_code=400,
            detail="Missing 'op' in advanced query clause. Must be one of: AND, OR, NOT",
        )

    operator_upper = operator.upper()
    if operator_upper not in VALID_OPERATORS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid operator '{operator}'. Must be one of: {', '.join(VALID_OPERATORS)}",
        )

    # Validate field - must be a non-empty string (Elasticsearch will validate the field exists)
    if not field:
        raise HTTPException(status_code=400, detail="Missing 'f' in advanced query clause")

    if not isinstance(field, str) or not field.strip():
        raise HTTPException(
            status_code=400,
            detail="'f' must be a non-empty string containing the Elasticsearch field name",
        )

    # Validate query
    if not query or not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="Missing or empty 'q' in advanced query clause")

    return {"operator": operator_upper, "field": field.strip(), "query": query.strip()}


def validate_adv_q(adv_q: Optional[List[dict]]) -> Optional[List[dict]]:
    """Validate and normalize advanced queries list.

    Args:
        adv_q: List of query clause dicts

    Returns:
        List of normalized query clause dicts

    Raises:
        HTTPException: If queries are invalid
    """
    if adv_q is None:
        return None

    if not isinstance(adv_q, list):
        raise HTTPException(
            status_code=400, detail="'adv_q' must be a list of query clause objects"
        )

    if len(adv_q) == 0:
        raise HTTPException(status_code=400, detail="'adv_q' cannot be an empty list")

    validated_queries = []
    for i, clause in enumerate(adv_q):
        try:
            validated_clause = validate_advanced_query_clause(clause)
            validated_queries.append(validated_clause)
        except HTTPException as e:
            raise HTTPException(
                status_code=e.status_code, detail=f"Error in adv_q[{i}]: {e.detail}"
            ) from e

    return validated_queries
