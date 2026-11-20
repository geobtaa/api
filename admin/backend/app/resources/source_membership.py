"""Resource Source identity is derived exclusively from its managing Set."""


def assertion_errors(record, source_id):
    """Allow round-trip identity assertions, never independent Source assignments."""
    if "source_id" in record and record["source_id"] != source_id:
        return [
            "source_id must match the managing Set's Source; change the managing Set to reassign"
        ]
    return []
