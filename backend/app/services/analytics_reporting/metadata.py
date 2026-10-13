"""Content labels are independent of member inventory eligibility."""


def content_metadata(record):
    # Corrections retain the original membership metadata beside refreshed labels.
    return record.get("content", record)


def content_providers(record):
    if not record or "provider" not in record:
        return ["Provider metadata unavailable"]
    value = record["provider"]
    values = value if isinstance(value, list) else [value]
    labels = [str(item).strip() for item in values if item is not None and str(item).strip()]
    return labels or ["Provider not recorded"]
