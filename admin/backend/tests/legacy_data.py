"""Frozen legacy rows for migration tests; never use retired application writers."""

from uuid import uuid4

from sqlalchemy import text


async def lifecycle(connection, *, resource_id=None):
    actor_id, lifecycle_id, event_id = uuid4(), uuid4(), uuid4()
    await connection.execute(
        text("""INSERT INTO actors (id, subject_key, kind, display_name)
        VALUES (:id, :subject, 'user', 'Legacy steward')"""),
        {"id": actor_id, "subject": str(actor_id)},
    )
    await connection.execute(
        text("""INSERT INTO lifecycles
        (lifecycle_id, code, title, created_by_actor_id, updated_by_actor_id)
        VALUES (:id, :code, 'Legacy collection', :actor, :actor)"""),
        {"id": lifecycle_id, "code": "legacy-" + lifecycle_id.hex, "actor": actor_id},
    )
    await connection.execute(
        text("""INSERT INTO lifecycle_activity_entries
        (id, lifecycle_id, actor_id, actor_display_name, action, software_version,
        correlation_id, idempotency_key, details)
        VALUES (:id, :scope, :actor, 'Legacy steward', 'lifecycle.created',
        'legacy-fixture', :id, :id, CAST(:details AS jsonb))"""),
        {"id": event_id, "scope": lifecycle_id, "actor": actor_id, "details": '{"lock_version":1}'},
    )
    if resource_id:
        await connection.execute(
            text("""INSERT INTO resources
            (id, lifecycle_id, publication_state, created_by_actor_id)
            VALUES (:id, :scope, 'draft', :actor)"""),
            {"id": resource_id, "scope": lifecycle_id, "actor": actor_id},
        )
    return lifecycle_id
