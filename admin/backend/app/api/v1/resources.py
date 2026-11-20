from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from pydantic import AfterValidator

from app.api.contracts import CSV_RESPONSE
from app.api.dependencies import Database, RequestKey, mutation_header
from app.auth import Actor, require_permissions
from app.csv_exchange import csv_line
from app.resources import (
    associations,
    bridge,
    create,
    csv_format,
    csv_io,
    distribution_csv,
    editor,
    intake,
    relationships,
    search,
    selections,
    service,
    source_linking,
)
from app.resources import preview as resource_preview
from app.resources.association_schemas import AssociationPage
from app.resources.csv_io import CsvCommit, CsvPreview, CsvRequest
from app.resources.schemas import (
    ConfirmPublishedEdit,
    CreatedResource,
    EditorContract,
    ImportCommit,
    ImportPreview,
    ImportRequest,
    ImportResult,
    PublishedEditPreview,
    ResourceCreate,
    ResourceDetailResponse,
    ResourcePage,
    ResourceUpdate,
)
from app.sets import membership
from app.sets.schemas import SetID
from app.url_ids import decode_id, encode_id

router = APIRouter(prefix="/admin/resources", tags=["resources"])
contract_router = APIRouter(prefix="/admin/contracts", tags=["contracts"])
local_router = APIRouter(prefix="/admin/resources", tags=["development fixtures"])
ResourceID = Annotated[
    str,
    Path(
        min_length=1,
        max_length=2733,
        description=(
            "Canonical URL key: ordinary IDs are literal; unsafe or reserved IDs use ~ "
            "plus unpadded base64url of UTF-8. Stored metadata IDs are unchanged."
        ),
    ),
    AfterValidator(decode_id),
]
Reader = Annotated[Actor, Depends(require_permissions("resources:read"))]
Importer = Annotated[Actor, Depends(require_permissions("resources:import"))]


@router.get(
    "/source-candidates",
    response_model=source_linking.SourceCandidatePage,
    operation_id="resources_source_candidates",
    summary="List Set reassignment candidates",
)
async def source_candidates(
    actor: Reader,
    database: Database,
    after: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
    set_id: SetID | None = None,
):
    """Page scoped Resource IDs, versions and legacy codes for reviewed Set reassignment.

    Requires human staff Resource read/associate, Set read, and Source read.
    Source ID is derived from the current managing Set.
    b1g_code_s falls back to the string value in immutable import evidence only when the
    relational code is null. No other evidence is exposed. Pass next_cursor as after;
    pages are live reads, not a snapshot. Set reassignment rechecks scope and versions.
    """
    return await source_linking.candidates(database, actor, after, limit, set_id)


@router.get(
    "", response_model=ResourcePage, operation_id="resources_list", summary="List resources"
)
async def index(
    actor: Reader,
    database: Database,
    q: Annotated[str, Query(max_length=200)] = "",
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    set_id: SetID | None = None,
    filters: Annotated[str, Query(description=search.FILTER_DESCRIPTION)] = "{}",
):
    """Search saved Resources within the actor's Set scope."""
    result = await service.list_resources(
        database, actor, q.strip(), offset, limit, set_id, search.parse_filters(filters)
    )

    result["can_create"] = create.can_create(actor)
    result["can_bulk_edit"] = editor.can_bulk_edit(actor)
    result["can_select"] = actor.kind == "user"
    result["can_validate"] = actor.kind == "user" and {
        "jobs:submit",
        "jobs:read",
        "sets:read",
    }.issubset(actor.permissions)
    return result


@router.post(
    "",
    status_code=201,
    response_model=CreatedResource,
    responses={
        201: {
            "headers": {
                "Location": {"description": "Canonical read URL", "schema": {"type": "string"}}
            }
        }
    },
    dependencies=[Depends(mutation_header)],
    operation_id="resources_create",
    summary="Create a Resource draft by hand",
)
async def create_resource(
    command: ResourceCreate,
    actor: Reader,
    database: Database,
    key: RequestKey,
    request: Request,
    response: Response,
):
    """Require staff Resource create/read and an accessible, non-retired Set if assigned.
    A successful create records the draft and Activity together. Duplicate IDs return 409.
    """
    result = await create.create_draft(
        database, actor, command, key, request.app.state.settings.app_version
    )
    response.headers["Location"] = f"/api/v1/admin/resources/{encode_id(result.id)}"
    return result


@router.post(
    "/imports/preview",
    response_model=ImportPreview,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_preview_import",
    summary="Preview JSON Resource import",
)
async def preview(command: ImportRequest, actor: Importer, database: Database):
    """Validate at most 100 JSON records without writes; existing IDs are skipped."""
    return await service.preview(database, actor, command)


@router.post(
    "/imports",
    response_model=ImportResult,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_import",
    summary="Confirm JSON Resource import",
)
async def commit(
    command: ImportCommit, actor: Importer, database: Database, key: RequestKey, request: Request
):
    """Confirm the unchanged preview; atomically create drafts, evidence, and Activity Log."""
    return await service.commit(
        database, actor, command, key, request.app.state.settings.app_version
    )


@contract_router.get(
    "/resources",
    response_model=EditorContract,
    operation_id="resources_editor_contract",
    summary="Get Resource editor contract",
)
async def editor_contract(actor: Reader):
    """Server-owned labels, field types, groups, vocabularies, and edit capability."""
    return editor.contract(actor)


@router.get(
    "/csv/crosswalk",
    response_class=Response,
    responses=CSV_RESPONSE,
    operation_id="resources_csv_crosswalk",
    summary="Download the Resource import column guide",
)
async def csv_crosswalk(actor: Reader):
    rows = csv_format.crosswalk(csv_io.columns(actor, "geomg"))
    return Response(
        csv_line(["CSV heading", "Technical field", "Import behavior"])
        + "".join(csv_line(r) for r in rows),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="resource-crosswalk.csv"'},
    )


@router.get(
    "/csv/distributions/template",
    response_class=Response,
    responses=CSV_RESPONSE,
    operation_id="distributions_csv_template",
    summary="Download Distribution link template",
)
async def distribution_template(actor: Reader):
    return Response(
        csv_line(distribution_csv.COLUMNS),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="distribution-template.csv"'},
    )


@router.get(
    "/csv/distributions/export",
    response_class=Response,
    responses=CSV_RESPONSE,
    operation_id="distributions_csv_export",
    summary="Export scoped Distribution links",
)
async def distribution_export(actor: Reader, database: Database, set_id: SetID | None = None):
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        distribution_csv.export(database, actor, set_id),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="distributions.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/csv/template",
    response_class=Response,
    responses={
        200: {
            "content": {"text/csv": {"schema": {"type": "string"}}},
            "description": "CSV header template download",
            "headers": {
                "Content-Disposition": {
                    "description": "Attachment filename",
                    "schema": {"type": "string"},
                }
            },
        }
    },
    operation_id="resources_csv_template",
    summary="Download CSV template",
)
async def csv_template(actor: Reader, format: Literal["technical", "geomg"] = "technical"):
    """Download technical or GEOMGv1-style headers, including explicit clear columns."""
    from fastapi.responses import Response

    return Response(
        csv_line(csv_io.columns(actor, format)),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="resource-template.csv"'},
    )


@router.get(
    "/csv/export",
    response_class=Response,
    responses={
        200: {
            "content": {"text/csv": {"schema": {"type": "string"}}},
            "description": "Streaming CSV download",
            "headers": {
                "Content-Disposition": {
                    "description": "Attachment filename",
                    "schema": {"type": "string"},
                }
            },
        }
    },
    operation_id="resources_csv_export",
    summary="Export Resources as CSV",
)
async def csv_export(
    actor: Reader,
    database: Database,
    q: Annotated[str, Query(max_length=200)] = "",
    set_id: SetID | None = None,
    filters: Annotated[str, Query(description=search.FILTER_DESCRIPTION)] = "{}",
    ids: Annotated[list[str] | None, Query()] = None,
    format: Literal["technical", "geomg"] = "technical",
):
    """Stream scoped Resources. GEOMG format uses readable headers and pipe-separated lists."""
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        csv_io.export(
            database, actor, q.strip(), set_id, ids, search.parse_filters(filters), format
        ),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="resources.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/csv/preview",
    response_model=CsvPreview,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_csv_preview",
    summary="Preview CSV import",
)
async def csv_preview(command: CsvRequest, actor: Importer, database: Database):
    """Preview draft creates, scoped or cross-Set updates, or ordered Distribution groups.

    Without a Set, confirmation creates catalog Resources immediately.
    Staff may assign those Resources to a Set later.
    By default, new IDs create drafts and matching IDs update editable drafts. An
    exported Lock Version is honored, otherwise preview pins the version.
    Resource files require the full template or GBL Admin primary export header. A missing column
    rejects the entire file. On updates, blank editable cells clear their fields.
    Add/replace link modes accept the
    four-column Distribution file and pin current Resource versions at preview.
    """
    return await csv_io.preview(database, actor, command)


@router.post(
    "/csv/import",
    response_model=CsvPreview,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_csv_import",
    summary="Confirm CSV import",
)
async def csv_import(
    command: CsvCommit, actor: Importer, database: Database, key: RequestKey, request: Request
):
    """Apply the confirmed preview atomically with per-record outcomes and safe retries."""
    return await csv_io.commit(
        database, actor, command, key, request.app.state.settings.app_version
    )


@router.get(
    "/csv/intake",
    response_model=list[intake.Batch],
    operation_id="resources_intake_list",
    summary="List accessible CSV uploads",
)
async def intake_list(
    actor: Importer,
    database: Database,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
):
    return await intake.list_batches(database, actor, offset, limit)


@router.get(
    "/csv/intake/{batch_id}",
    response_model=intake.DraftPage,
    operation_id="resources_intake_drafts",
    summary="List pending drafts in an upload",
)
async def intake_drafts(
    batch_id: UUID,
    actor: Importer,
    database: Database,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await intake.list_drafts(database, actor, batch_id, offset, limit)


@router.get(
    "/csv/intake/{batch_id}/receipt",
    response_model=CsvPreview,
    operation_id="resources_intake_receipt",
    summary="Read original upload outcomes",
)
async def intake_receipt(batch_id: UUID, actor: Importer, database: Database):
    return await intake.receipt(database, actor, batch_id)


@router.patch(
    "/csv/intake/{batch_id}/rows/{number}",
    response_model=intake.Draft,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_intake_edit",
    summary="Edit a pending CSV draft",
)
async def intake_edit(
    batch_id: UUID,
    number: int,
    command: intake.Edit,
    actor: Importer,
    database: Database,
    key: RequestKey,
):
    return await intake.edit(database, actor, batch_id, number, command, key)


@router.post(
    "/csv/intake/{batch_id}/assignments/preview",
    response_model=CsvPreview,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_intake_preview",
    summary="Preview assignment of pending drafts",
)
async def intake_preview(
    batch_id: UUID, command: intake.Assignment, actor: Importer, database: Database
):
    return await intake.assign(database, actor, batch_id, command)


@router.post(
    "/csv/intake/{batch_id}/assignments",
    response_model=CsvPreview,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_intake_assign",
    summary="Confirm assignment of pending drafts",
)
async def intake_assign(
    batch_id: UUID,
    command: intake.ConfirmAssignment,
    actor: Importer,
    database: Database,
    key: RequestKey,
    request: Request,
):
    return await intake.assign(
        database, actor, batch_id, command, key, request.app.state.settings.app_version
    )


@router.get(
    "/facets",
    response_model=list[search.FacetDefinition],
    operation_id="resources_facet_contract",
    summary="List Resource facets",
)
async def facet_contract(actor: Reader):
    """GEOMGv1 sidebar facets; legacy filter keys remain supported for saved URLs."""
    return [{"field": field, "label": search.FACETS[field][0]} for field in search.SIDEBAR_FACETS]


@router.get(
    "/facets/{field}",
    response_model=search.FacetPage,
    operation_id="resources_facet_values",
    summary="List facet values",
)
async def facet_values(
    field: str,
    actor: Reader,
    database: Database,
    q: str = "",
    set_id: SetID | None = None,
    filters: Annotated[str, Query(description=search.FILTER_DESCRIPTION)] = "{}",
    term: str = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: search.FacetSort = "count_desc",
):
    """Search/page facet counts within actor scope, excluding this field's selections."""
    return await search.facets(
        database, actor, field, q.strip(), set_id, filters, term.strip(), offset, limit, sort
    )


@local_router.post(
    "/bridge/batches",
    response_model=bridge.BridgeResult,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_bridge_batch",
    summary="Stage a local Bridge batch",
)
async def bridge_batch(
    command: bridge.BridgeBatch,
    actor: Importer,
    database: Database,
    key: RequestKey,
    request: Request,
):
    """Local create-only Bridge staging; atomic aggregate writes and replayable batch outcomes."""
    if request.app.state.settings.app_env not in {"development", "test"}:
        from app.domain import DomainError

        raise DomainError(403, "local_only", "Bridge staging is only available locally")
    return await bridge.commit(
        database, actor, command, key, request.app.state.settings.app_version
    )


@router.post(
    "/selections",
    status_code=201,
    responses={
        201: {
            "headers": {
                "Location": {"description": "Canonical read URL", "schema": {"type": "string"}}
            }
        }
    },
    response_model=selections.SelectionSummary,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_snapshot_selection",
    summary="Create immutable Resource selection",
)
async def snapshot_selection(
    response: Response,
    command: selections.SelectionRequest,
    actor: Reader,
    database: Database,
    key: RequestKey,
):
    """Snapshot all matching IDs and versions with the shared search predicates."""
    result = await selections.create(database, actor, command, key)
    response.headers["Location"] = f"/api/v1/admin/resources/selections/{result['selection_id']}"
    return result


@router.get(
    "/selections/{selection_id}",
    response_model=selections.SelectionPage,
    operation_id="resources_selection_page",
    summary="Get Resource selection",
)
async def selection_page(
    selection_id: UUID,
    actor: Reader,
    database: Database,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    return await selections.page(database, actor, selection_id, offset, limit)


@router.get(
    "/{resource_id}",
    response_model=ResourceDetailResponse,
    operation_id="resources_get",
    summary="Get a Resource",
)
async def detail(actor: Reader, database: Database, resource_id: ResourceID):
    """Read canonical draft metadata and separate, immutable import evidence."""
    return await service.detail(database, actor, resource_id)


@router.patch(
    "/{resource_id}",
    response_model=ResourceDetailResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_update_resource",
    summary="Update a Resource",
)
async def update_resource(
    command: ResourceUpdate,
    actor: Reader,
    database: Database,
    key: RequestKey,
    request: Request,
    resource_id: ResourceID,
):
    """Selectively edit a draft with explicit clears, concurrency, and atomic Activity Log."""
    return await editor.edit(
        database, actor, resource_id, command, key, request.app.state.settings.app_version
    )


@router.get(
    "/{resource_id}/metadata",
    response_model=dict[str, object],
    operation_id="resources_preview_metadata",
    summary="Get Resource preview metadata",
)
async def preview_metadata(
    actor: Reader,
    database: Database,
    resource_id: ResourceID,
):
    """Saved Aardvark metadata for OGM Viewer; excludes internal administration and evidence."""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        await resource_preview.record(database, actor, resource_id),
        headers={"Cache-Control": "no-store"},
    )


@router.get(
    "/{resource_id}/associations/{family}",
    response_model=AssociationPage,
    operation_id="resources_resource_associations",
    summary="List Resource association rows",
)
async def resource_associations(
    family: Literal[
        "relationships",
        "downloads",
        "licensed-accesses",
        "assets",
        "data-dictionaries",
        "dictionary-entries",
    ],
    actor: Reader,
    database: Database,
    response: Response,
    resource_id: ResourceID,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
):
    """Read association rows within Set scope; staff Resource editor access is required.

    Includes protected dictionary staff notes and licensed-access metadata. Not a
    public delivery endpoint. Relationships are outgoing edges, without resolving
    or exposing target Resource records. Mutations are not part of this contract.
    """
    response.headers["Cache-Control"] = "no-store"
    return await associations.page(database, actor, resource_id, family, offset, limit)


@router.get(
    "/{resource_id}/relationships",
    response_model=relationships.RelationshipPage,
    operation_id="resources_relationship_navigation",
    summary="List Resource relationships",
)
async def relationship_navigation(
    actor: Reader,
    database: Database,
    response: Response,
    resource_id: ResourceID,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
):
    """Navigate saved metadata relationships and visible inverse links; no stored edge writes."""
    response.headers["Cache-Control"] = "no-store"
    return await relationships.page(database, actor, resource_id, offset, limit)


@router.put(
    "/{resource_id}/set",
    response_model=membership.AssociationResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_associate",
    summary="Assign or change a Resource's managing Set",
)
async def associate(
    command: membership.Association,
    actor: Reader,
    database: Database,
    key: RequestKey,
    request: Request,
    resource_id: ResourceID,
):
    """Confirm a versioned assignment with a reason. Send an explicit null source_set_id
    to assign a visible unassigned draft. The destination Set records the Activity.
    Reassignment between Sets requires access to both and records Activity on each.
    """
    return await membership.associate(
        database, actor, resource_id, command, key, request.app.state.settings.app_version
    )


@router.post(
    "/{resource_id}/published-edits/preview",
    response_model=PublishedEditPreview,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_preview_published_edit",
)
async def preview_published_edit(
    command: ResourceUpdate,
    actor: Reader,
    database: Database,
    request: Request,
    resource_id: ResourceID,
):
    """Preview public metadata changes to a single visible published Resource."""
    return await editor.edit(
        database,
        actor,
        resource_id,
        command,
        None,
        request.app.state.settings.app_version,
        dry_run=True,
        published=True,
    )


@router.post(
    "/{resource_id}/published-edits",
    response_model=ResourceDetailResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="resources_confirm_published_edit",
)
async def confirm_published_edit(
    command: ConfirmPublishedEdit,
    actor: Reader,
    database: Database,
    request: Request,
    resource_id: ResourceID,
    key: RequestKey,
):
    """Confirm the exact preview and atomically enqueue projection of the committed version."""
    return await editor.edit(
        database,
        actor,
        resource_id,
        command.edit,
        key,
        request.app.state.settings.app_version,
        published=True,
        preview_id=command.preview_id,
    )
