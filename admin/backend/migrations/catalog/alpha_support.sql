-- Frozen supporting objects from GEOMG Alembic alpha_bridge_01, generated from an empty database.
-- Existing data-api catalog tables, sequences, ACLs and migration history remain in place.
CREATE FUNCTION public.lifecycle_activity_immutable() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            RAISE EXCEPTION 'Activity entries are append-only';
        END $$;

CREATE FUNCTION public.lifecycle_immutable_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.code IS DISTINCT FROM OLD.code THEN
                RAISE EXCEPTION 'Lifecycle codes are immutable';
            END IF;
            RETURN NEW;
        END $$;

CREATE FUNCTION public.protect_job() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Job history is permanent'; END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.workflow_version_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM workflow_versions WHERE version_id = NEW.workflow_version_id
            AND state = 'active'
        ) THEN RAISE EXCEPTION 'Jobs require an active version at submission'; END IF;
        RETURN NEW;
    END IF;
    IF OLD.state NOT IN ('queued', 'running') OR
        (to_jsonb(OLD) - ARRAY['state','attempt_number','lease_token','lease_until','finished_at'])
        IS DISTINCT FROM
        (to_jsonb(NEW) - ARRAY['state','attempt_number','lease_token','lease_until','finished_at'])
    THEN RAISE EXCEPTION 'Job identity and terminal history are immutable'; END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION public.protect_job_item() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE parent_state text;
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Job results are permanent'; END IF;
    SELECT state INTO parent_state FROM jobs WHERE job_id = NEW.job_id FOR UPDATE;
    IF parent_state NOT IN ('queued', 'running') THEN
        RAISE EXCEPTION 'Terminal job results are immutable';
    END IF;
    IF TG_OP = 'UPDATE' AND (OLD.disposition <> 'pending' OR
        (to_jsonb(OLD) - ARRAY['disposition','details']) IS DISTINCT FROM
        (to_jsonb(NEW) - ARRAY['disposition','details'])) THEN
        RAISE EXCEPTION 'Selected versions and completed results are immutable';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION public.protect_report_chunk() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE parent_state text; expires timestamptz;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'Report bytes are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN
                SELECT expires_at INTO expires FROM job_artifacts
                    WHERE artifact_id = OLD.artifact_id;
                IF expires > clock_timestamp() THEN
                    RAISE EXCEPTION 'Report retention has not elapsed';
                END IF;
                RETURN OLD;
            END IF;
            SELECT j.state INTO parent_state FROM jobs j JOIN job_artifacts a
                ON a.job_id = j.job_id WHERE a.artifact_id = NEW.artifact_id;
            IF parent_state NOT IN ('queued', 'running') THEN
                RAISE EXCEPTION 'Completed report bytes are immutable';
            END IF;
            RETURN NEW;
        END $$;

CREATE FUNCTION public.protect_resource_selection_item() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE frozen boolean;
BEGIN
    IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Selected versions are immutable'; END IF;
    SELECT sealed INTO frozen FROM resource_selections
    WHERE selection_id = NEW.selection_id FOR SHARE;
    IF frozen THEN RAISE EXCEPTION 'Selection is sealed'; END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION public.protect_set_cutover() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN
        RAISE EXCEPTION 'Set ownership cutover evidence is immutable'; END $$;

CREATE FUNCTION public.seal_resource_selection() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Selections are retained'; END IF;
    IF OLD.sealed OR NOT NEW.sealed OR (to_jsonb(OLD) - 'sealed') IS DISTINCT FROM
    (to_jsonb(NEW) - 'sealed') THEN RAISE EXCEPTION 'Selections are immutable'; END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION public.set_identity_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
IF NEW.set_id IS DISTINCT FROM OLD.set_id OR NEW.source_id IS DISTINCT FROM OLD.source_id
 OR NEW.created_at IS DISTINCT FROM OLD.created_at
 OR NEW.created_by_actor_id IS DISTINCT FROM OLD.created_by_actor_id THEN
 RAISE EXCEPTION 'Set identity, parent Source and creation attribution are immutable';
END IF; RETURN NEW; END $$;

CREATE FUNCTION public.source_identity_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.source_id IS DISTINCT FROM OLD.source_id
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.created_by_actor_id IS DISTINCT FROM OLD.created_by_actor_id THEN
                RAISE EXCEPTION 'Source identity and creation attribution are immutable';
            END IF;
            RETURN NEW;
        END $$;

CREATE FUNCTION public.work_event_immutable() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN RAISE EXCEPTION 'Work event history is immutable'; END $$;

CREATE FUNCTION public.work_task_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
IF OLD.status IN ('completed','cancelled') THEN
 RAISE EXCEPTION 'Terminal Task occurrences are immutable';
END IF;
IF NEW.task_id IS DISTINCT FROM OLD.task_id OR NEW.set_id IS DISTINCT FROM OLD.set_id
 OR NEW.work_type IS DISTINCT FROM OLD.work_type OR NEW.recurring IS DISTINCT FROM OLD.recurring
 OR NEW.predecessor_id IS DISTINCT FROM OLD.predecessor_id
 OR NEW.created_at IS DISTINCT FROM OLD.created_at
 OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id THEN
 RAISE EXCEPTION 'Task identity, subject and creation evidence are immutable';
END IF;
RETURN NEW;
END $$;

CREATE FUNCTION public.workflow_identity_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.workflow_id <> OLD.workflow_id OR NEW.lifecycle_id <> OLD.lifecycle_id THEN
                RAISE EXCEPTION 'Workflow identity and Lifecycle are immutable';
            END IF;
            RETURN NEW;
        END $$;

CREATE FUNCTION public.workflow_process_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE parent_state text;
        BEGIN
            IF TG_OP = 'UPDATE' AND NEW.version_id <> OLD.version_id THEN
                RAISE EXCEPTION 'Processes cannot move between versions';
            END IF;
            IF TG_OP = 'DELETE' THEN
                SELECT state INTO parent_state FROM workflow_versions
                WHERE version_id = OLD.version_id FOR UPDATE;
            ELSE
                SELECT state INTO parent_state FROM workflow_versions
                WHERE version_id = NEW.version_id FOR UPDATE;
            END IF;
            IF parent_state IS DISTINCT FROM 'draft' THEN
                RAISE EXCEPTION 'Only draft processes can change';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;

CREATE FUNCTION public.workflow_version_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.state <> 'draft' THEN RAISE EXCEPTION 'Versions begin as drafts'; END IF;
                RETURN NEW;
            END IF;
            IF OLD.state = 'superseded' THEN
                RAISE EXCEPTION 'Superseded versions are immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN
                IF OLD.state <> 'draft' THEN
                    RAISE EXCEPTION 'Active versions are immutable';
                END IF;
                RETURN OLD;
            END IF;
            IF OLD.state = 'active' THEN
                IF NEW.state <> 'superseded' OR
                   (to_jsonb(NEW) - 'state') IS DISTINCT FROM (to_jsonb(OLD) - 'state') THEN
                    RAISE EXCEPTION 'Active definitions are immutable';
                END IF;
            ELSE
                IF NEW.version_id <> OLD.version_id OR NEW.workflow_id <> OLD.workflow_id OR
                   NEW.number <> OLD.number OR NEW.created_at <> OLD.created_at OR
                   NEW.created_by_actor_id <> OLD.created_by_actor_id THEN
                    RAISE EXCEPTION 'Version identity is immutable';
                END IF;
                IF NEW.state NOT IN ('draft', 'active') THEN
                    RAISE EXCEPTION 'Invalid version transition';
                END IF;
                IF NEW.state = 'active' AND NOT EXISTS (
                    SELECT 1 FROM workflow_processes WHERE version_id = OLD.version_id
                ) THEN RAISE EXCEPTION 'Activation requires a process'; END IF;
            END IF;
            RETURN NEW;
        END $$;

SET default_tablespace = '';

SET default_table_access_method = heap;

CREATE TABLE public.actors (
    id uuid NOT NULL,
    subject_key text NOT NULL,
    kind text NOT NULL,
    display_name text NOT NULL,
    CONSTRAINT actors_kind CHECK ((kind = ANY (ARRAY['user'::text, 'service_account'::text, 'system'::text])))
);

CREATE TABLE public.alpha_bridge_evidence (
    batch_id uuid NOT NULL,
    ordinal integer NOT NULL,
    resource_id text,
    outcome text NOT NULL,
    source_record jsonb NOT NULL
);

CREATE TABLE public.alpha_bridge_membership (
    resource_id text NOT NULL,
    set_id character varying(128) NOT NULL,
    origin text NOT NULL,
    CONSTRAINT alpha_bridge_membership_origin_check CHECK ((origin = ANY (ARRAY['production'::text, 'pilot'::text])))
);

CREATE TABLE public.alpha_bridge_receipts (
    batch_id uuid NOT NULL,
    request_hash text NOT NULL,
    result jsonb NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.alpha_bridge_state (
    resource_id text NOT NULL,
    resource_version integer NOT NULL,
    source_hash text NOT NULL,
    source_updated_at timestamp with time zone NOT NULL,
    source_record jsonb NOT NULL
);

CREATE TABLE public.alpha_catalog_seed (
    singleton boolean NOT NULL,
    scope_hash text NOT NULL,
    pilot_hash text NOT NULL,
    pilot_count integer NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT alpha_catalog_seed_singleton_check CHECK (singleton)
);

CREATE TABLE public.identity_accounts (
    actor_id uuid NOT NULL,
    lock_version integer DEFAULT 1 NOT NULL,
    active boolean DEFAULT true NOT NULL,
    all_lifecycles boolean DEFAULT false NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    all_sets boolean DEFAULT false NOT NULL
);

CREATE TABLE public.identity_invitations (
    invitation_id uuid NOT NULL,
    token_hash character varying(64) NOT NULL,
    idp_entity_id text NOT NULL,
    permissions text[] NOT NULL,
    lifecycle_ids uuid[] NOT NULL,
    all_lifecycles boolean NOT NULL,
    created_by_actor_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    redeemed_by_actor_id uuid,
    redeemed_at timestamp with time zone,
    revoked_at timestamp with time zone,
    all_sets boolean DEFAULT false NOT NULL,
    set_ids text[] DEFAULT '{}'::text[] NOT NULL,
    CONSTRAINT invitation_expiry CHECK ((expires_at > created_at))
);

CREATE TABLE public.identity_lifecycle_grants (
    actor_id uuid NOT NULL,
    lifecycle_id uuid NOT NULL
);

CREATE TABLE public.identity_local_credentials (
    actor_id uuid NOT NULL,
    email character varying(254) NOT NULL,
    password_hash text,
    setup_hash character varying(64),
    setup_expires_at timestamp with time zone
);

CREATE TABLE public.identity_login_limits (
    bucket character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    attempts integer NOT NULL
);

CREATE TABLE public.identity_permissions (
    actor_id uuid NOT NULL,
    permission character varying(100) NOT NULL
);

CREATE TABLE public.identity_sessions (
    token_hash character varying(64) NOT NULL,
    actor_id uuid NOT NULL,
    authentication_context text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT session_expiry CHECK ((expires_at > created_at))
);

CREATE TABLE public.identity_set_grants (
    actor_id uuid NOT NULL,
    set_id character varying(128) NOT NULL
);

CREATE TABLE public.job_artifact_chunks (
    artifact_id uuid NOT NULL,
    "position" integer NOT NULL,
    content bytea NOT NULL,
    CONSTRAINT artifact_chunk_bound CHECK ((("position" > 0) AND ((octet_length(content) >= 1) AND (octet_length(content) <= 65536))))
);

CREATE TABLE public.job_artifacts (
    artifact_id uuid NOT NULL,
    job_id uuid NOT NULL,
    checksum character varying(64) NOT NULL,
    byte_count bigint NOT NULL,
    content bytea,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    expired_at timestamp with time zone,
    CONSTRAINT job_artifact_size CHECK (((byte_count >= 0) AND ((content IS NULL) OR (octet_length(content) = byte_count))))
);

CREATE TABLE public.job_attempts (
    job_id uuid NOT NULL,
    number integer NOT NULL,
    lease_token uuid NOT NULL,
    state text NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    CONSTRAINT job_attempt_state CHECK ((state = ANY (ARRAY['running'::text, 'expired'::text, 'succeeded'::text, 'partially_succeeded'::text, 'failed'::text, 'cancelled'::text, 'rejected'::text])))
);

CREATE TABLE public.job_items (
    job_id uuid NOT NULL,
    "position" integer NOT NULL,
    resource_id character varying(512) NOT NULL,
    resource_version integer NOT NULL,
    disposition text DEFAULT 'pending'::text NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT job_item_bounds CHECK ((("position" > 0) AND (resource_version > 0))),
    CONSTRAINT job_item_details_bound CHECK ((octet_length((details)::text) <= 16384)),
    CONSTRAINT job_item_disposition CHECK ((disposition = ANY (ARRAY['pending'::text, 'unchanged'::text, 'conflicted'::text, 'invalid'::text, 'failed'::text, 'cancelled'::text, 'rejected'::text])))
);

CREATE TABLE public.jobs (
    job_id uuid NOT NULL,
    lifecycle_id uuid,
    actor_id uuid NOT NULL,
    operation text NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash character varying(64) NOT NULL,
    workflow_id uuid,
    workflow_version_id uuid,
    state text DEFAULT 'queued'::text NOT NULL,
    attempt_number integer DEFAULT 0 NOT NULL,
    lease_token uuid,
    lease_until timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    software_version character varying(100) NOT NULL,
    set_id character varying(128) NOT NULL,
    CONSTRAINT job_attempt_limit CHECK (((attempt_number >= 0) AND (attempt_number <= 3))),
    CONSTRAINT job_lease CHECK (((state = 'running'::text) = ((lease_token IS NOT NULL) AND (lease_until IS NOT NULL)))),
    CONSTRAINT job_operation CHECK ((operation = 'resources.validate'::text)),
    CONSTRAINT job_state CHECK ((state = ANY (ARRAY['queued'::text, 'running'::text, 'succeeded'::text, 'partially_succeeded'::text, 'failed'::text, 'cancelled'::text, 'rejected'::text]))),
    CONSTRAINT job_workflow_pair CHECK (((workflow_id IS NULL) = (workflow_version_id IS NULL)))
);

CREATE TABLE public.lifecycle_activity_entries (
    id uuid NOT NULL,
    lifecycle_id uuid,
    actor_id uuid NOT NULL,
    actor_display_name text NOT NULL,
    action text NOT NULL,
    outcome text DEFAULT 'succeeded'::text NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    origin text DEFAULT 'geomg-admin'::text NOT NULL,
    software_version text NOT NULL,
    correlation_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    reason text,
    details jsonb NOT NULL,
    workflow_id uuid,
    workflow_version_id uuid,
    job_id uuid,
    resource_id text,
    source_id character varying(128),
    set_id character varying(128),
    CONSTRAINT activity_action CHECK (((action = ANY (ARRAY['lifecycle.created'::text, 'lifecycle.updated'::text, 'resources.imported'::text, 'resource.updated'::text, 'lifecycle.paused'::text, 'lifecycle.activated'::text, 'lifecycle.retired'::text, 'lifecycle.restored'::text, 'review.completed'::text, 'harvest.completed'::text, 'workflow.created'::text, 'workflow.updated'::text, 'workflow.draft_created'::text, 'workflow.activated'::text, 'validation.completed'::text, 'lifecycle.representative_changed'::text, 'resource.associated'::text, 'source.created'::text, 'source.updated'::text, 'set.created'::text, 'set.updated'::text, 'set.deactivated'::text, 'set.activated'::text, 'set.retired'::text, 'set.restored'::text, 'set.representative_changed'::text, 'set.migrated'::text])) OR (action = 'resource.created'::text))),
    CONSTRAINT activity_outcome CHECK ((outcome = ANY (ARRAY['succeeded'::text, 'partially_succeeded'::text, 'failed'::text, 'cancelled'::text, 'rejected'::text]))),
    CONSTRAINT activity_subject CHECK (
CASE
    WHEN (action = 'resource.created'::text) THEN ((resource_id IS NOT NULL) AND (source_id IS NULL) AND (lifecycle_id IS NULL) AND (workflow_id IS NULL) AND (workflow_version_id IS NULL) AND (job_id IS NULL))
    ELSE (((set_id IS NULL) AND (source_id IS NULL) AND (lifecycle_id IS NOT NULL) AND (action <> ALL (ARRAY['source.created'::text, 'source.updated'::text, 'set.created'::text, 'set.updated'::text, 'set.deactivated'::text, 'set.activated'::text, 'set.retired'::text, 'set.restored'::text, 'set.representative_changed'::text, 'set.migrated'::text]))) OR ((set_id IS NULL) AND (source_id IS NOT NULL) AND (lifecycle_id IS NULL) AND (action = ANY (ARRAY['source.created'::text, 'source.updated'::text, 'review.completed'::text, 'harvest.completed'::text])) AND (resource_id IS NULL) AND (workflow_id IS NULL) AND (workflow_version_id IS NULL) AND (job_id IS NULL)) OR ((set_id IS NOT NULL) AND (source_id IS NULL) AND (lifecycle_id IS NULL) AND (action !~~ 'lifecycle.%'::text) AND (action <> ALL (ARRAY['source.created'::text, 'source.updated'::text]))) OR ((set_id IS NULL) AND (source_id IS NULL) AND (lifecycle_id IS NULL) AND (resource_id IS NOT NULL) AND (workflow_id IS NULL) AND (job_id IS NULL) AND (action = ANY (ARRAY['resources.imported'::text, 'resource.updated'::text]))))
END),
    CONSTRAINT activity_workflow_pair CHECK (((workflow_id IS NULL) = (workflow_version_id IS NULL)))
);

CREATE TABLE public.lifecycle_commands (
    actor_id uuid NOT NULL,
    operation text NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash character varying(64) NOT NULL,
    response jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.lifecycles (
    lifecycle_id uuid NOT NULL,
    code character varying(63) NOT NULL,
    title character varying(250) NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    endpoint_url text,
    source_description text DEFAULT ''::text NOT NULL,
    admin_notes text DEFAULT ''::text NOT NULL,
    tags text[] DEFAULT '{}'::text[] NOT NULL,
    review_interval interval,
    harvest_interval interval,
    lock_version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by_actor_id uuid NOT NULL,
    updated_by_actor_id uuid NOT NULL,
    review_anchor_at timestamp with time zone,
    harvest_anchor_at timestamp with time zone,
    represented_by_id text,
    workflow_catalog_id character varying(128),
    CONSTRAINT lifecycle_code CHECK ((((code)::text ~ '^[a-z0-9]+(-[a-z0-9]+)*$'::text) AND (length((code)::text) >= 3))),
    CONSTRAINT lifecycle_harvest_interval CHECK (((harvest_interval IS NULL) OR ((EXTRACT(epoch FROM harvest_interval) > (0)::numeric) AND ((((EXTRACT(year FROM harvest_interval) * (12)::numeric) + EXTRACT(month FROM harvest_interval)) >= (0)::numeric) AND (((EXTRACT(year FROM harvest_interval) * (12)::numeric) + EXTRACT(month FROM harvest_interval)) <= (12000)::numeric)) AND ((EXTRACT(day FROM harvest_interval) >= (0)::numeric) AND (EXTRACT(day FROM harvest_interval) <= (7000)::numeric)) AND (EXTRACT(hour FROM harvest_interval) = (0)::numeric) AND (EXTRACT(minute FROM harvest_interval) = (0)::numeric) AND (EXTRACT(second FROM harvest_interval) = (0)::numeric) AND ((EXTRACT(day FROM harvest_interval) = (0)::numeric) OR ((EXTRACT(year FROM harvest_interval) = (0)::numeric) AND (EXTRACT(month FROM harvest_interval) = (0)::numeric)))))),
    CONSTRAINT lifecycle_review_interval CHECK (((review_interval IS NULL) OR ((EXTRACT(epoch FROM review_interval) > (0)::numeric) AND ((((EXTRACT(year FROM review_interval) * (12)::numeric) + EXTRACT(month FROM review_interval)) >= (0)::numeric) AND (((EXTRACT(year FROM review_interval) * (12)::numeric) + EXTRACT(month FROM review_interval)) <= (12000)::numeric)) AND ((EXTRACT(day FROM review_interval) >= (0)::numeric) AND (EXTRACT(day FROM review_interval) <= (7000)::numeric)) AND (EXTRACT(hour FROM review_interval) = (0)::numeric) AND (EXTRACT(minute FROM review_interval) = (0)::numeric) AND (EXTRACT(second FROM review_interval) = (0)::numeric) AND ((EXTRACT(day FROM review_interval) = (0)::numeric) OR ((EXTRACT(year FROM review_interval) = (0)::numeric) AND (EXTRACT(month FROM review_interval) = (0)::numeric)))))),
    CONSTRAINT lifecycle_status CHECK ((status = ANY (ARRAY['active'::text, 'paused'::text, 'retired'::text]))),
    CONSTRAINT lifecycle_tags CHECK ((cardinality(tags) <= 20)),
    CONSTRAINT lifecycle_title CHECK ((length(btrim((title)::text)) > 0)),
    CONSTRAINT lifecycle_version CHECK ((lock_version > 0))
);

CREATE TABLE public.resource_bulk_actions (
    id uuid NOT NULL,
    selection_id uuid NOT NULL,
    reverts uuid,
    actor_id uuid NOT NULL,
    actor_name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    key uuid NOT NULL,
    request_hash character varying(64) NOT NULL,
    fields jsonb NOT NULL
);

CREATE TABLE public.resource_bulk_executions (
    action_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    actor_name text NOT NULL,
    applied_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);

CREATE TABLE public.resource_bulk_items (
    action_id uuid NOT NULL,
    resource_id text NOT NULL,
    set_id character varying(128),
    before_version integer NOT NULL,
    status text NOT NULL,
    changes jsonb NOT NULL,
    CONSTRAINT resource_bulk_items_before_version_check CHECK ((before_version > 0)),
    CONSTRAINT resource_bulk_items_status_check CHECK ((status = ANY (ARRAY['ready'::text, 'unchanged'::text, 'conflict'::text, 'read_only'::text, 'active_job'::text])))
);

CREATE TABLE public.resource_bulk_results (
    action_id uuid NOT NULL,
    resource_id text NOT NULL,
    status text NOT NULL,
    after_version integer,
    CONSTRAINT resource_bulk_results_check CHECK (((status = 'changed'::text) = (after_version IS NOT NULL))),
    CONSTRAINT resource_bulk_results_status_check CHECK ((status = ANY (ARRAY['changed'::text, 'unchanged'::text, 'conflict'::text, 'read_only'::text, 'active_job'::text])))
);

CREATE TABLE public.resource_import_evidence (
    resource_id character varying NOT NULL,
    import_id uuid NOT NULL,
    source_record jsonb NOT NULL,
    warnings text[] NOT NULL
);

CREATE TABLE public.resource_imports (
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    lifecycle_id uuid,
    request_hash character varying(64) NOT NULL,
    response jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    set_id character varying(128),
    intake_batch_id uuid,
    CONSTRAINT resource_import_owner CHECK (((set_id IS NOT NULL) OR (lifecycle_id IS NOT NULL) OR (intake_batch_id IS NOT NULL)))
);

CREATE TABLE public.resource_intake_activity (
    id uuid NOT NULL,
    batch_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    action text NOT NULL,
    details jsonb NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT resource_intake_activity_action_check CHECK ((action = ANY (ARRAY['saved'::text, 'edited'::text, 'assigned'::text])))
);

CREATE TABLE public.resource_intake_batches (
    id uuid NOT NULL,
    actor_id uuid NOT NULL,
    receipt_key uuid NOT NULL,
    original_csv text NOT NULL,
    headings jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.resource_intake_drafts (
    batch_id uuid NOT NULL,
    row_number integer NOT NULL,
    resource_id text NOT NULL,
    title text NOT NULL,
    cells jsonb NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    assigned_import uuid,
    catalog_id text,
    CONSTRAINT resource_intake_drafts_row_number_check CHECK ((row_number > 0)),
    CONSTRAINT resource_intake_drafts_version_check CHECK ((version > 0))
);

CREATE TABLE public.resource_projection_requests (
    resource_id character varying NOT NULL,
    resource_version integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    next_attempt_at timestamp with time zone DEFAULT now() NOT NULL,
    visible_at timestamp with time zone
);

CREATE TABLE public.resource_selection_items (
    selection_id uuid NOT NULL,
    resource_id character varying(512) NOT NULL,
    lifecycle_id uuid,
    resource_version integer NOT NULL,
    set_id character varying(128)
);

CREATE TABLE public.resource_selections (
    selection_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash character varying(64) NOT NULL,
    sealed boolean DEFAULT false NOT NULL,
    query jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.resource_set_cutovers (
    resource_id text NOT NULL,
    cutover_id uuid NOT NULL,
    lifecycle_id uuid NOT NULL,
    source_id character varying(128),
    set_id character varying(128) NOT NULL,
    target_source_id character varying(128) NOT NULL,
    resource_version integer NOT NULL,
    original_updated_at timestamp with time zone NOT NULL,
    reason text NOT NULL,
    source_reconciliation text
);

CREATE TABLE public.security_audit (
    event_id uuid NOT NULL,
    actor_id uuid,
    target_actor_id uuid,
    action text NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT security_action CHECK ((action = ANY (ARRAY['invitation.created'::text, 'invitation.revoked'::text, 'invitation.redeemed'::text, 'session.created'::text, 'session.revoked'::text, 'account.changed'::text, 'signin.rejected'::text])))
);

CREATE TABLE public.set_commands (
    actor_id uuid NOT NULL,
    operation text NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash character varying(64) NOT NULL,
    response jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.set_maintenance (
    set_id character varying(128) NOT NULL,
    work_type character varying(16) NOT NULL,
    "interval" character varying(16) NOT NULL,
    next_due_on date,
    enabled boolean DEFAULT true NOT NULL,
    assignee_id uuid,
    lock_version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT maintenance_interval CHECK ((("interval")::text ~ '^P[1-9][0-9]{0,2}[DWMY]$|^P1000[DWMY]$'::text)),
    CONSTRAINT maintenance_version CHECK ((lock_version > 0)),
    CONSTRAINT maintenance_work_type CHECK (((work_type)::text = ANY ((ARRAY['review'::character varying, 'ingest'::character varying])::text[])))
);

CREATE TABLE public.set_ownership_cutovers (
    cutover_id uuid NOT NULL,
    manifest_hash character varying(64) NOT NULL,
    preview_hash character varying(64) NOT NULL,
    reviewed_by character varying(250) NOT NULL,
    reason text NOT NULL,
    manifest jsonb NOT NULL,
    resource_count bigint NOT NULL,
    preserved_imports bigint NOT NULL,
    preserved_selections bigint NOT NULL,
    recorded_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL
);

CREATE TABLE public.sets (
    set_id character varying(128) NOT NULL,
    source_id character varying(128) NOT NULL,
    title character varying(250) NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    endpoint_url character varying(2048),
    admin_notes text DEFAULT ''::text NOT NULL,
    legacy_code text DEFAULT ''::text NOT NULL,
    set_scope text DEFAULT ''::text NOT NULL,
    endpoint_description text DEFAULT ''::text NOT NULL,
    workflow text DEFAULT ''::text NOT NULL,
    review_interval text DEFAULT ''::text NOT NULL,
    harvest_interval text DEFAULT ''::text NOT NULL,
    tags text DEFAULT ''::text NOT NULL,
    status character varying(16) DEFAULT 'active'::character varying NOT NULL,
    lock_version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by_actor_id uuid NOT NULL,
    updated_by_actor_id uuid NOT NULL,
    workflow_catalog_id character varying(128),
    represented_by_id text,
    CONSTRAINT set_description_bound CHECK ((length(description) <= 5000)),
    CONSTRAINT set_endpoint_description_bound CHECK ((length(endpoint_description) <= 1000)),
    CONSTRAINT set_harvest_interval_bound CHECK ((length(harvest_interval) <= 64)),
    CONSTRAINT set_id_format CHECK (((set_id)::text ~ '^[A-Za-z0-9_-]{1,128}$'::text)),
    CONSTRAINT set_legacy_code_bound CHECK ((length(legacy_code) <= 128)),
    CONSTRAINT set_notes_bound CHECK ((length(admin_notes) <= 10000)),
    CONSTRAINT set_review_interval_bound CHECK ((length(review_interval) <= 64)),
    CONSTRAINT set_set_scope_bound CHECK ((length(set_scope) <= 5000)),
    CONSTRAINT set_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'inactive'::character varying, 'retired'::character varying])::text[]))),
    CONSTRAINT set_tags_bound CHECK ((length(tags) <= 2000)),
    CONSTRAINT set_title CHECK ((length(btrim((title)::text)) > 0)),
    CONSTRAINT set_version CHECK ((lock_version > 0)),
    CONSTRAINT set_workflow_bound CHECK ((length(workflow) <= 128))
);

CREATE TABLE public.source_commands (
    actor_id uuid NOT NULL,
    operation text NOT NULL,
    idempotency_key uuid NOT NULL,
    request_hash character varying(64) NOT NULL,
    response jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE public.sources (
    source_id character varying(128) NOT NULL,
    title character varying(250) NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    landing_page character varying(2048),
    admin_notes text DEFAULT ''::text NOT NULL,
    lock_version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by_actor_id uuid NOT NULL,
    updated_by_actor_id uuid NOT NULL,
    legacy_code character varying(128),
    CONSTRAINT source_description_bound CHECK ((length(description) <= 5000)),
    CONSTRAINT source_id_format CHECK (((source_id)::text ~ '^[A-Za-z0-9_-]{1,128}$'::text)),
    CONSTRAINT source_notes_bound CHECK ((length(admin_notes) <= 10000)),
    CONSTRAINT source_title CHECK ((length(btrim((title)::text)) > 0)),
    CONSTRAINT source_version CHECK ((lock_version > 0))
);

CREATE TABLE public.work_periods (
    period_id uuid NOT NULL,
    name character varying(120) NOT NULL,
    starts_on date NOT NULL,
    ends_on date NOT NULL,
    lock_version integer DEFAULT 1 NOT NULL,
    created_by_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT period_name CHECK ((length(btrim((name)::text)) > 0)),
    CONSTRAINT period_range CHECK ((ends_on >= starts_on)),
    CONSTRAINT period_version CHECK ((lock_version > 0))
);

CREATE TABLE public.work_task_events (
    event_id uuid NOT NULL,
    task_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    actor_name text NOT NULL,
    action character varying(32) NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    details jsonb NOT NULL
);

CREATE TABLE public.work_tasks (
    task_id uuid NOT NULL,
    set_id character varying(128) NOT NULL,
    work_type character varying(16) NOT NULL,
    title character varying(250) NOT NULL,
    description text DEFAULT ''::text NOT NULL,
    status character varying(16) DEFAULT 'open'::character varying NOT NULL,
    due_on date NOT NULL,
    planned_on date,
    assignee_id uuid,
    recurring boolean DEFAULT false NOT NULL,
    predecessor_id uuid,
    lock_version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by_id uuid NOT NULL,
    completed_at timestamp with time zone,
    completion_recorded_at timestamp with time zone,
    completed_by_id uuid,
    completion_summary text,
    evidence jsonb DEFAULT '[]'::jsonb NOT NULL,
    processed_count integer DEFAULT 0 NOT NULL,
    changed_count integer DEFAULT 0 NOT NULL,
    CONSTRAINT task_completion CHECK (((((status)::text = 'completed'::text) AND (completed_at IS NOT NULL) AND (completion_recorded_at IS NOT NULL) AND (completed_by_id IS NOT NULL) AND (length(btrim(completion_summary)) > 0) AND (completed_at <= completion_recorded_at)) OR (((status)::text <> 'completed'::text) AND (completed_at IS NULL) AND (completion_recorded_at IS NULL) AND (completed_by_id IS NULL) AND (completion_summary IS NULL)))),
    CONSTRAINT task_counts CHECK (((processed_count >= 0) AND ((changed_count >= 0) AND (changed_count <= processed_count)))),
    CONSTRAINT task_recurrence_type CHECK (((NOT recurring) OR ((work_type)::text = ANY ((ARRAY['review'::character varying, 'ingest'::character varying])::text[])))),
    CONSTRAINT task_status CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'in_progress'::character varying, 'blocked'::character varying, 'completed'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT task_title CHECK (((length(btrim((title)::text)) >= 1) AND (length(btrim((title)::text)) <= 250))),
    CONSTRAINT task_version CHECK ((lock_version > 0)),
    CONSTRAINT task_work_type CHECK (((work_type)::text = ANY ((ARRAY['review'::character varying, 'ingest'::character varying, 'other'::character varying])::text[])))
);

CREATE TABLE public.workflow_catalog (
    workflow_id character varying(128) NOT NULL,
    label character varying(250) NOT NULL,
    description text NOT NULL,
    acquisition_mode character varying(64) NOT NULL,
    CONSTRAINT workflow_catalog_id_format CHECK (((workflow_id)::text ~ '^[A-Za-z0-9_-]{1,128}$'::text)),
    CONSTRAINT workflow_catalog_label CHECK ((length(btrim((label)::text)) > 0)),
    CONSTRAINT workflow_catalog_mode CHECK (((acquisition_mode)::text = ANY ((ARRAY['automated_retrieval'::character varying, 'mediated_deposit'::character varying, 'manual_curation'::character varying])::text[])))
);

CREATE TABLE public.workflow_process_types (
    key text NOT NULL,
    label text NOT NULL,
    definition text NOT NULL
);

CREATE TABLE public.workflow_processes (
    process_id uuid NOT NULL,
    version_id uuid NOT NULL,
    "position" integer NOT NULL,
    process_type text NOT NULL,
    name character varying(200) NOT NULL,
    configuration_schema_version integer DEFAULT 1 NOT NULL,
    configuration jsonb NOT NULL,
    CONSTRAINT workflow_configuration_bound CHECK (((jsonb_typeof(configuration) = 'object'::text) AND (octet_length((configuration)::text) <= 8192))),
    CONSTRAINT workflow_configuration_version CHECK ((configuration_schema_version = 1)),
    CONSTRAINT workflow_process_position CHECK ((("position" >= 1) AND ("position" <= 100)))
);

CREATE TABLE public.workflow_versions (
    version_id uuid NOT NULL,
    workflow_id uuid NOT NULL,
    number integer NOT NULL,
    state text DEFAULT 'draft'::text NOT NULL,
    checksum character varying(64),
    created_by_actor_id uuid NOT NULL,
    activated_by_actor_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    activated_at timestamp with time zone,
    CONSTRAINT workflow_activation_evidence CHECK (((state = 'draft'::text) OR ((checksum IS NOT NULL) AND (activated_at IS NOT NULL) AND (activated_by_actor_id IS NOT NULL)))),
    CONSTRAINT workflow_version_number CHECK ((number > 0)),
    CONSTRAINT workflow_version_state CHECK ((state = ANY (ARRAY['draft'::text, 'active'::text, 'superseded'::text])))
);

CREATE TABLE public.workflows (
    workflow_id uuid NOT NULL,
    lifecycle_id uuid,
    title character varying(250) NOT NULL,
    lock_version integer DEFAULT 1 NOT NULL,
    created_by_actor_id uuid NOT NULL,
    updated_by_actor_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    set_id character varying(128) NOT NULL,
    CONSTRAINT workflow_lock_version CHECK ((lock_version > 0)),
    CONSTRAINT workflow_title CHECK ((length(btrim((title)::text)) > 0))
);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT activity_set_replay UNIQUE (actor_id, set_id, action, idempotency_key);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT activity_source_replay UNIQUE (actor_id, source_id, action, idempotency_key);

ALTER TABLE ONLY public.actors
    ADD CONSTRAINT actors_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.actors
    ADD CONSTRAINT actors_subject_key UNIQUE (kind, subject_key);

ALTER TABLE ONLY public.alpha_bridge_evidence
    ADD CONSTRAINT alpha_bridge_evidence_pkey PRIMARY KEY (batch_id, ordinal);

ALTER TABLE ONLY public.alpha_bridge_membership
    ADD CONSTRAINT alpha_bridge_membership_pkey PRIMARY KEY (resource_id);

ALTER TABLE ONLY public.alpha_bridge_receipts
    ADD CONSTRAINT alpha_bridge_receipts_pkey PRIMARY KEY (batch_id);

ALTER TABLE ONLY public.alpha_bridge_state
    ADD CONSTRAINT alpha_bridge_state_pkey PRIMARY KEY (resource_id);

ALTER TABLE ONLY public.alpha_catalog_seed
    ADD CONSTRAINT alpha_catalog_seed_pkey PRIMARY KEY (singleton);

ALTER TABLE ONLY public.identity_accounts
    ADD CONSTRAINT identity_accounts_pkey PRIMARY KEY (actor_id);

ALTER TABLE ONLY public.identity_invitations
    ADD CONSTRAINT identity_invitations_pkey PRIMARY KEY (invitation_id);

ALTER TABLE ONLY public.identity_invitations
    ADD CONSTRAINT identity_invitations_token_hash_key UNIQUE (token_hash);

ALTER TABLE ONLY public.identity_lifecycle_grants
    ADD CONSTRAINT identity_lifecycle_grants_pkey PRIMARY KEY (actor_id, lifecycle_id);

ALTER TABLE ONLY public.identity_local_credentials
    ADD CONSTRAINT identity_local_credentials_email_key UNIQUE (email);

ALTER TABLE ONLY public.identity_local_credentials
    ADD CONSTRAINT identity_local_credentials_pkey PRIMARY KEY (actor_id);

ALTER TABLE ONLY public.identity_local_credentials
    ADD CONSTRAINT identity_local_credentials_setup_hash_key UNIQUE (setup_hash);

ALTER TABLE ONLY public.identity_login_limits
    ADD CONSTRAINT identity_login_limits_pkey PRIMARY KEY (bucket);

ALTER TABLE ONLY public.identity_permissions
    ADD CONSTRAINT identity_permissions_pkey PRIMARY KEY (actor_id, permission);

ALTER TABLE ONLY public.identity_sessions
    ADD CONSTRAINT identity_sessions_pkey PRIMARY KEY (token_hash);

ALTER TABLE ONLY public.identity_set_grants
    ADD CONSTRAINT identity_set_grants_pkey PRIMARY KEY (actor_id, set_id);

ALTER TABLE ONLY public.job_artifact_chunks
    ADD CONSTRAINT job_artifact_chunks_pkey PRIMARY KEY (artifact_id, "position");

ALTER TABLE ONLY public.job_artifacts
    ADD CONSTRAINT job_artifacts_job_id_key UNIQUE (job_id);

ALTER TABLE ONLY public.job_artifacts
    ADD CONSTRAINT job_artifacts_pkey PRIMARY KEY (artifact_id);

ALTER TABLE ONLY public.job_attempts
    ADD CONSTRAINT job_attempts_lease_token_key UNIQUE (lease_token);

ALTER TABLE ONLY public.job_attempts
    ADD CONSTRAINT job_attempts_pkey PRIMARY KEY (job_id, number);

ALTER TABLE ONLY public.job_items
    ADD CONSTRAINT job_items_job_id_resource_id_key UNIQUE (job_id, resource_id);

ALTER TABLE ONLY public.job_items
    ADD CONSTRAINT job_items_pkey PRIMARY KEY (job_id, "position");

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT job_set_identity UNIQUE (set_id, job_id);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT job_set_receipt UNIQUE (actor_id, set_id, operation, idempotency_key);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_actor_id_lifecycle_id_operation_idempotency_key_key UNIQUE (actor_id, lifecycle_id, operation, idempotency_key);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_lifecycle_id_job_id_key UNIQUE (lifecycle_id, job_id);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (job_id);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT lifecycle_activity_entries_actor_id_lifecycle_id_action_ide_key UNIQUE (actor_id, lifecycle_id, action, idempotency_key);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT lifecycle_activity_entries_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.lifecycle_commands
    ADD CONSTRAINT lifecycle_commands_pkey PRIMARY KEY (actor_id, operation, idempotency_key);

ALTER TABLE ONLY public.lifecycles
    ADD CONSTRAINT lifecycles_code_key UNIQUE (code);

ALTER TABLE ONLY public.lifecycles
    ADD CONSTRAINT lifecycles_pkey PRIMARY KEY (lifecycle_id);

ALTER TABLE ONLY public.resource_bulk_actions
    ADD CONSTRAINT resource_bulk_actions_actor_id_key_key UNIQUE (actor_id, key);

ALTER TABLE ONLY public.resource_bulk_actions
    ADD CONSTRAINT resource_bulk_actions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_bulk_executions
    ADD CONSTRAINT resource_bulk_executions_pkey PRIMARY KEY (action_id);

ALTER TABLE ONLY public.resource_bulk_items
    ADD CONSTRAINT resource_bulk_items_pkey PRIMARY KEY (action_id, resource_id);

ALTER TABLE ONLY public.resource_bulk_results
    ADD CONSTRAINT resource_bulk_results_pkey PRIMARY KEY (action_id, resource_id);

ALTER TABLE ONLY public.resource_import_evidence
    ADD CONSTRAINT resource_import_evidence_pkey PRIMARY KEY (resource_id);

ALTER TABLE ONLY public.resource_imports
    ADD CONSTRAINT resource_imports_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_intake_activity
    ADD CONSTRAINT resource_intake_activity_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_intake_batches
    ADD CONSTRAINT resource_intake_batches_actor_id_receipt_key_key UNIQUE (actor_id, receipt_key);

ALTER TABLE ONLY public.resource_intake_batches
    ADD CONSTRAINT resource_intake_batches_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.resource_intake_drafts
    ADD CONSTRAINT resource_intake_drafts_catalog_id_key UNIQUE (catalog_id);

ALTER TABLE ONLY public.resource_intake_drafts
    ADD CONSTRAINT resource_intake_drafts_pkey PRIMARY KEY (batch_id, row_number);

ALTER TABLE ONLY public.resource_projection_requests
    ADD CONSTRAINT resource_projection_requests_pkey PRIMARY KEY (resource_id, resource_version);

ALTER TABLE ONLY public.resource_selection_items
    ADD CONSTRAINT resource_selection_items_pkey PRIMARY KEY (selection_id, resource_id);

ALTER TABLE ONLY public.resource_selections
    ADD CONSTRAINT resource_selections_actor_id_idempotency_key_key UNIQUE (actor_id, idempotency_key);

ALTER TABLE ONLY public.resource_selections
    ADD CONSTRAINT resource_selections_pkey PRIMARY KEY (selection_id);

ALTER TABLE ONLY public.resource_set_cutovers
    ADD CONSTRAINT resource_set_cutovers_pkey PRIMARY KEY (resource_id);

ALTER TABLE ONLY public.security_audit
    ADD CONSTRAINT security_audit_pkey PRIMARY KEY (event_id);

ALTER TABLE ONLY public.set_commands
    ADD CONSTRAINT set_commands_pkey PRIMARY KEY (actor_id, operation, idempotency_key);

ALTER TABLE ONLY public.set_maintenance
    ADD CONSTRAINT set_maintenance_pkey PRIMARY KEY (set_id, work_type);

ALTER TABLE ONLY public.set_ownership_cutovers
    ADD CONSTRAINT set_ownership_cutovers_manifest_hash_key UNIQUE (manifest_hash);

ALTER TABLE ONLY public.set_ownership_cutovers
    ADD CONSTRAINT set_ownership_cutovers_pkey PRIMARY KEY (cutover_id);

ALTER TABLE ONLY public.sets
    ADD CONSTRAINT sets_pkey PRIMARY KEY (set_id);

ALTER TABLE ONLY public.source_commands
    ADD CONSTRAINT source_commands_pkey PRIMARY KEY (actor_id, operation, idempotency_key);

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (source_id);

ALTER TABLE ONLY public.work_periods
    ADD CONSTRAINT work_periods_name_key UNIQUE (name);

ALTER TABLE ONLY public.work_periods
    ADD CONSTRAINT work_periods_pkey PRIMARY KEY (period_id);

ALTER TABLE ONLY public.work_task_events
    ADD CONSTRAINT work_task_events_pkey PRIMARY KEY (event_id);

ALTER TABLE ONLY public.work_tasks
    ADD CONSTRAINT work_tasks_pkey PRIMARY KEY (task_id);

ALTER TABLE ONLY public.work_tasks
    ADD CONSTRAINT work_tasks_predecessor_id_key UNIQUE (predecessor_id);

ALTER TABLE ONLY public.workflow_catalog
    ADD CONSTRAINT workflow_catalog_pkey PRIMARY KEY (workflow_id);

ALTER TABLE ONLY public.workflow_process_types
    ADD CONSTRAINT workflow_process_types_pkey PRIMARY KEY (key);

ALTER TABLE ONLY public.workflow_processes
    ADD CONSTRAINT workflow_processes_pkey PRIMARY KEY (process_id);

ALTER TABLE ONLY public.workflow_processes
    ADD CONSTRAINT workflow_processes_version_id_position_key UNIQUE (version_id, "position");

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflow_set_identity UNIQUE (set_id, workflow_id);

ALTER TABLE ONLY public.workflow_versions
    ADD CONSTRAINT workflow_versions_pkey PRIMARY KEY (version_id);

ALTER TABLE ONLY public.workflow_versions
    ADD CONSTRAINT workflow_versions_workflow_id_number_key UNIQUE (workflow_id, number);

ALTER TABLE ONLY public.workflow_versions
    ADD CONSTRAINT workflow_versions_workflow_id_version_id_key UNIQUE (workflow_id, version_id);

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_lifecycle_id_workflow_id_key UNIQUE (lifecycle_id, workflow_id);

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_pkey PRIMARY KEY (workflow_id);

CREATE INDEX activity_lifecycle_time ON public.lifecycle_activity_entries USING btree (lifecycle_id, occurred_at, id);

CREATE INDEX activity_set_time ON public.lifecycle_activity_entries USING btree (set_id, occurred_at, id);

CREATE INDEX activity_source_time ON public.lifecycle_activity_entries USING btree (source_id, occurred_at, id);

CREATE INDEX alpha_bridge_review ON public.alpha_bridge_evidence USING btree (outcome, resource_id);

CREATE INDEX intake_owner_date ON public.resource_intake_batches USING btree (actor_id, created_at);

CREATE INDEX ix_identity_login_limits_expires_at ON public.identity_login_limits USING btree (expires_at);

CREATE INDEX jobs_claim ON public.jobs USING btree (state, lease_until, created_at, job_id);

CREATE INDEX lifecycles_title_id ON public.lifecycles USING btree (lower((title)::text), lifecycle_id);

CREATE UNIQUE INDEX one_open_recurrence ON public.work_tasks USING btree (set_id, work_type) WHERE (recurring AND ((status)::text = ANY ((ARRAY['open'::character varying, 'in_progress'::character varying, 'blocked'::character varying])::text[])));

CREATE INDEX resource_bulk_history ON public.resource_bulk_actions USING btree (actor_id, created_at, id);

CREATE INDEX resource_set_cutover_scope ON public.resource_set_cutovers USING btree (set_id, lifecycle_id);

CREATE INDEX sets_source_id ON public.sets USING btree (source_id);

CREATE INDEX sets_title_id ON public.sets USING btree (lower((title)::text), set_id);

CREATE INDEX sources_legacy_code ON public.sources USING btree (legacy_code, source_id);

CREATE INDEX sources_title_id ON public.sources USING btree (lower((title)::text), source_id);

CREATE INDEX task_event_time ON public.work_task_events USING btree (task_id, recorded_at, event_id);

CREATE INDEX tasks_assignee ON public.work_tasks USING btree (assignee_id, status, due_on);

CREATE INDEX tasks_completed ON public.work_tasks USING btree (completed_at, task_id);

CREATE INDEX tasks_queue ON public.work_tasks USING btree (status, due_on, task_id);

CREATE INDEX tasks_set_due ON public.work_tasks USING btree (set_id, due_on);

CREATE UNIQUE INDEX workflow_one_active ON public.workflow_versions USING btree (workflow_id) WHERE (state = 'active'::text);

CREATE UNIQUE INDEX workflow_one_draft ON public.workflow_versions USING btree (workflow_id) WHERE (state = 'draft'::text);

CREATE INDEX workflows_lifecycle_title ON public.workflows USING btree (lifecycle_id, title, workflow_id);

CREATE INDEX workflows_set_title ON public.workflows USING btree (set_id, title, workflow_id);

CREATE TRIGGER immutable_bulk_history BEFORE DELETE OR UPDATE ON public.resource_bulk_actions FOR EACH ROW EXECUTE FUNCTION public.lifecycle_activity_immutable();

CREATE TRIGGER immutable_bulk_history BEFORE DELETE OR UPDATE ON public.resource_bulk_executions FOR EACH ROW EXECUTE FUNCTION public.lifecycle_activity_immutable();

CREATE TRIGGER immutable_bulk_history BEFORE DELETE OR UPDATE ON public.resource_bulk_items FOR EACH ROW EXECUTE FUNCTION public.lifecycle_activity_immutable();

CREATE TRIGGER immutable_bulk_history BEFORE DELETE OR UPDATE ON public.resource_bulk_results FOR EACH ROW EXECUTE FUNCTION public.lifecycle_activity_immutable();

CREATE TRIGGER lifecycle_activity_append_only BEFORE DELETE OR UPDATE ON public.lifecycle_activity_entries FOR EACH ROW EXECUTE FUNCTION public.lifecycle_activity_immutable();

CREATE TRIGGER lifecycle_code_immutable BEFORE UPDATE ON public.lifecycles FOR EACH ROW EXECUTE FUNCTION public.lifecycle_immutable_code();

CREATE TRIGGER protect_job BEFORE INSERT OR DELETE OR UPDATE ON public.jobs FOR EACH ROW EXECUTE FUNCTION public.protect_job();

CREATE TRIGGER protect_job_item BEFORE INSERT OR DELETE OR UPDATE ON public.job_items FOR EACH ROW EXECUTE FUNCTION public.protect_job_item();

CREATE TRIGGER protect_report_chunk BEFORE INSERT OR DELETE OR UPDATE ON public.job_artifact_chunks FOR EACH ROW EXECUTE FUNCTION public.protect_report_chunk();

CREATE TRIGGER protect_resource_selection_item BEFORE INSERT OR DELETE OR UPDATE ON public.resource_selection_items FOR EACH ROW EXECUTE FUNCTION public.protect_resource_selection_item();

CREATE TRIGGER protect_set_cutover BEFORE DELETE OR UPDATE ON public.resource_set_cutovers FOR EACH ROW EXECUTE FUNCTION public.protect_set_cutover();

CREATE TRIGGER protect_set_cutover BEFORE DELETE OR UPDATE ON public.set_ownership_cutovers FOR EACH ROW EXECUTE FUNCTION public.protect_set_cutover();

CREATE TRIGGER seal_resource_selection BEFORE DELETE OR UPDATE ON public.resource_selections FOR EACH ROW EXECUTE FUNCTION public.seal_resource_selection();

CREATE TRIGGER set_identity_immutable BEFORE UPDATE ON public.sets FOR EACH ROW EXECUTE FUNCTION public.set_identity_guard();

CREATE TRIGGER source_identity_immutable BEFORE UPDATE ON public.sources FOR EACH ROW EXECUTE FUNCTION public.source_identity_guard();

CREATE TRIGGER work_event_immutable BEFORE DELETE OR UPDATE ON public.work_task_events FOR EACH ROW EXECUTE FUNCTION public.work_event_immutable();

CREATE TRIGGER work_task_guard BEFORE UPDATE ON public.work_tasks FOR EACH ROW EXECUTE FUNCTION public.work_task_guard();

CREATE TRIGGER workflow_identity_immutable BEFORE UPDATE ON public.workflows FOR EACH ROW EXECUTE FUNCTION public.workflow_identity_guard();

CREATE TRIGGER workflow_process_immutable BEFORE INSERT OR DELETE OR UPDATE ON public.workflow_processes FOR EACH ROW EXECUTE FUNCTION public.workflow_process_guard();

CREATE TRIGGER workflow_version_immutable BEFORE INSERT OR DELETE OR UPDATE ON public.workflow_versions FOR EACH ROW EXECUTE FUNCTION public.workflow_version_guard();

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT activity_job_lifecycle FOREIGN KEY (lifecycle_id, job_id) REFERENCES public.jobs(lifecycle_id, job_id);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT activity_resource_identity FOREIGN KEY (resource_id) REFERENCES public.resources(id);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT activity_set_job FOREIGN KEY (set_id, job_id) REFERENCES public.jobs(set_id, job_id);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT activity_set_workflow FOREIGN KEY (set_id, workflow_id) REFERENCES public.workflows(set_id, workflow_id);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT activity_workflow_lifecycle FOREIGN KEY (lifecycle_id, workflow_id) REFERENCES public.workflows(lifecycle_id, workflow_id);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT activity_workflow_version FOREIGN KEY (workflow_id, workflow_version_id) REFERENCES public.workflow_versions(workflow_id, version_id);

ALTER TABLE ONLY public.alpha_bridge_evidence
    ADD CONSTRAINT alpha_bridge_evidence_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.alpha_bridge_receipts(batch_id);

ALTER TABLE ONLY public.alpha_bridge_membership
    ADD CONSTRAINT alpha_bridge_membership_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.alpha_bridge_state
    ADD CONSTRAINT alpha_bridge_state_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id);

ALTER TABLE ONLY public.identity_accounts
    ADD CONSTRAINT identity_accounts_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.identity_invitations
    ADD CONSTRAINT identity_invitations_created_by_actor_id_fkey FOREIGN KEY (created_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.identity_invitations
    ADD CONSTRAINT identity_invitations_redeemed_by_actor_id_fkey FOREIGN KEY (redeemed_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.identity_lifecycle_grants
    ADD CONSTRAINT identity_lifecycle_grants_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.identity_accounts(actor_id);

ALTER TABLE ONLY public.identity_lifecycle_grants
    ADD CONSTRAINT identity_lifecycle_grants_lifecycle_id_fkey FOREIGN KEY (lifecycle_id) REFERENCES public.lifecycles(lifecycle_id);

ALTER TABLE ONLY public.identity_local_credentials
    ADD CONSTRAINT identity_local_credentials_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.identity_accounts(actor_id);

ALTER TABLE ONLY public.identity_permissions
    ADD CONSTRAINT identity_permissions_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.identity_accounts(actor_id);

ALTER TABLE ONLY public.identity_sessions
    ADD CONSTRAINT identity_sessions_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.identity_accounts(actor_id);

ALTER TABLE ONLY public.identity_set_grants
    ADD CONSTRAINT identity_set_grants_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.identity_accounts(actor_id);

ALTER TABLE ONLY public.identity_set_grants
    ADD CONSTRAINT identity_set_grants_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.job_artifact_chunks
    ADD CONSTRAINT job_artifact_chunks_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES public.job_artifacts(artifact_id);

ALTER TABLE ONLY public.job_artifacts
    ADD CONSTRAINT job_artifacts_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(job_id);

ALTER TABLE ONLY public.job_attempts
    ADD CONSTRAINT job_attempts_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(job_id);

ALTER TABLE ONLY public.job_items
    ADD CONSTRAINT job_items_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(job_id);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT job_set_workflow FOREIGN KEY (set_id, workflow_id) REFERENCES public.workflows(set_id, workflow_id);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_lifecycle_id_fkey FOREIGN KEY (lifecycle_id) REFERENCES public.lifecycles(lifecycle_id);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_lifecycle_id_workflow_id_fkey FOREIGN KEY (lifecycle_id, workflow_id) REFERENCES public.workflows(lifecycle_id, workflow_id);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_workflow_id_workflow_version_id_fkey FOREIGN KEY (workflow_id, workflow_version_id) REFERENCES public.workflow_versions(workflow_id, version_id);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT lifecycle_activity_entries_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT lifecycle_activity_entries_lifecycle_id_fkey FOREIGN KEY (lifecycle_id) REFERENCES public.lifecycles(lifecycle_id);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT lifecycle_activity_entries_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.lifecycle_activity_entries
    ADD CONSTRAINT lifecycle_activity_entries_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(source_id);

ALTER TABLE ONLY public.lifecycle_commands
    ADD CONSTRAINT lifecycle_commands_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.lifecycles
    ADD CONSTRAINT lifecycle_representative FOREIGN KEY (represented_by_id) REFERENCES public.resources(id);

ALTER TABLE ONLY public.lifecycles
    ADD CONSTRAINT lifecycles_created_by_actor_id_fkey FOREIGN KEY (created_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.lifecycles
    ADD CONSTRAINT lifecycles_updated_by_actor_id_fkey FOREIGN KEY (updated_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.lifecycles
    ADD CONSTRAINT lifecycles_workflow_catalog_id_fkey FOREIGN KEY (workflow_catalog_id) REFERENCES public.workflow_catalog(workflow_id);

ALTER TABLE ONLY public.resource_bulk_actions
    ADD CONSTRAINT resource_bulk_actions_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.resource_bulk_actions
    ADD CONSTRAINT resource_bulk_actions_reverts_fkey FOREIGN KEY (reverts) REFERENCES public.resource_bulk_actions(id);

ALTER TABLE ONLY public.resource_bulk_actions
    ADD CONSTRAINT resource_bulk_actions_selection_id_fkey FOREIGN KEY (selection_id) REFERENCES public.resource_selections(selection_id);

ALTER TABLE ONLY public.resource_bulk_executions
    ADD CONSTRAINT resource_bulk_executions_action_id_fkey FOREIGN KEY (action_id) REFERENCES public.resource_bulk_actions(id);

ALTER TABLE ONLY public.resource_bulk_executions
    ADD CONSTRAINT resource_bulk_executions_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.resource_bulk_items
    ADD CONSTRAINT resource_bulk_items_action_id_fkey FOREIGN KEY (action_id) REFERENCES public.resource_bulk_actions(id);

ALTER TABLE ONLY public.resource_bulk_items
    ADD CONSTRAINT resource_bulk_items_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.resource_bulk_results
    ADD CONSTRAINT resource_bulk_results_action_id_fkey FOREIGN KEY (action_id) REFERENCES public.resource_bulk_executions(action_id);

ALTER TABLE ONLY public.resource_bulk_results
    ADD CONSTRAINT resource_bulk_results_action_id_resource_id_fkey FOREIGN KEY (action_id, resource_id) REFERENCES public.resource_bulk_items(action_id, resource_id);

ALTER TABLE ONLY public.resource_import_evidence
    ADD CONSTRAINT resource_import_evidence_import_id_fkey FOREIGN KEY (import_id) REFERENCES public.resource_imports(id);

ALTER TABLE ONLY public.resource_imports
    ADD CONSTRAINT resource_imports_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.resource_imports
    ADD CONSTRAINT resource_imports_intake_batch_id_fkey FOREIGN KEY (intake_batch_id) REFERENCES public.resource_intake_batches(id);

ALTER TABLE ONLY public.resource_imports
    ADD CONSTRAINT resource_imports_lifecycle_id_fkey FOREIGN KEY (lifecycle_id) REFERENCES public.lifecycles(lifecycle_id);

ALTER TABLE ONLY public.resource_imports
    ADD CONSTRAINT resource_imports_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.resource_intake_activity
    ADD CONSTRAINT resource_intake_activity_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.resource_intake_activity
    ADD CONSTRAINT resource_intake_activity_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.resource_intake_batches(id);

ALTER TABLE ONLY public.resource_intake_batches
    ADD CONSTRAINT resource_intake_batches_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.resource_intake_drafts
    ADD CONSTRAINT resource_intake_drafts_assigned_import_fkey FOREIGN KEY (assigned_import) REFERENCES public.resource_imports(id);

ALTER TABLE ONLY public.resource_intake_drafts
    ADD CONSTRAINT resource_intake_drafts_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.resource_intake_batches(id);

ALTER TABLE ONLY public.resource_intake_drafts
    ADD CONSTRAINT resource_intake_drafts_catalog_id_fkey FOREIGN KEY (catalog_id) REFERENCES public.resources(id);

ALTER TABLE ONLY public.resource_projection_requests
    ADD CONSTRAINT resource_projection_requests_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id);

ALTER TABLE ONLY public.resource_selection_items
    ADD CONSTRAINT resource_selection_items_lifecycle_id_fkey FOREIGN KEY (lifecycle_id) REFERENCES public.lifecycles(lifecycle_id);

ALTER TABLE ONLY public.resource_selection_items
    ADD CONSTRAINT resource_selection_items_selection_id_fkey FOREIGN KEY (selection_id) REFERENCES public.resource_selections(selection_id);

ALTER TABLE ONLY public.resource_selection_items
    ADD CONSTRAINT resource_selection_items_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.resource_selections
    ADD CONSTRAINT resource_selections_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.resource_set_cutovers
    ADD CONSTRAINT resource_set_cutovers_cutover_id_fkey FOREIGN KEY (cutover_id) REFERENCES public.set_ownership_cutovers(cutover_id);

ALTER TABLE ONLY public.resource_set_cutovers
    ADD CONSTRAINT resource_set_cutovers_lifecycle_id_fkey FOREIGN KEY (lifecycle_id) REFERENCES public.lifecycles(lifecycle_id);

ALTER TABLE ONLY public.resource_set_cutovers
    ADD CONSTRAINT resource_set_cutovers_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(id);

ALTER TABLE ONLY public.resource_set_cutovers
    ADD CONSTRAINT resource_set_cutovers_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.resource_set_cutovers
    ADD CONSTRAINT resource_set_cutovers_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(source_id);

ALTER TABLE ONLY public.resource_set_cutovers
    ADD CONSTRAINT resource_set_cutovers_target_source_id_fkey FOREIGN KEY (target_source_id) REFERENCES public.sources(source_id);

ALTER TABLE ONLY public.security_audit
    ADD CONSTRAINT security_audit_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.security_audit
    ADD CONSTRAINT security_audit_target_actor_id_fkey FOREIGN KEY (target_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.set_commands
    ADD CONSTRAINT set_commands_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.set_maintenance
    ADD CONSTRAINT set_maintenance_assignee_id_fkey FOREIGN KEY (assignee_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.set_maintenance
    ADD CONSTRAINT set_maintenance_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.sets
    ADD CONSTRAINT set_representative FOREIGN KEY (represented_by_id) REFERENCES public.resources(id);

ALTER TABLE ONLY public.sets
    ADD CONSTRAINT sets_created_by_actor_id_fkey FOREIGN KEY (created_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.sets
    ADD CONSTRAINT sets_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(source_id);

ALTER TABLE ONLY public.sets
    ADD CONSTRAINT sets_updated_by_actor_id_fkey FOREIGN KEY (updated_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.sets
    ADD CONSTRAINT sets_workflow_catalog_id_fkey FOREIGN KEY (workflow_catalog_id) REFERENCES public.workflow_catalog(workflow_id);

ALTER TABLE ONLY public.source_commands
    ADD CONSTRAINT source_commands_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_created_by_actor_id_fkey FOREIGN KEY (created_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_updated_by_actor_id_fkey FOREIGN KEY (updated_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.work_periods
    ADD CONSTRAINT work_periods_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.work_task_events
    ADD CONSTRAINT work_task_events_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.work_task_events
    ADD CONSTRAINT work_task_events_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.work_tasks(task_id);

ALTER TABLE ONLY public.work_tasks
    ADD CONSTRAINT work_tasks_assignee_id_fkey FOREIGN KEY (assignee_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.work_tasks
    ADD CONSTRAINT work_tasks_completed_by_id_fkey FOREIGN KEY (completed_by_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.work_tasks
    ADD CONSTRAINT work_tasks_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.work_tasks
    ADD CONSTRAINT work_tasks_predecessor_id_fkey FOREIGN KEY (predecessor_id) REFERENCES public.work_tasks(task_id);

ALTER TABLE ONLY public.work_tasks
    ADD CONSTRAINT work_tasks_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.workflow_processes
    ADD CONSTRAINT workflow_processes_process_type_fkey FOREIGN KEY (process_type) REFERENCES public.workflow_process_types(key);

ALTER TABLE ONLY public.workflow_processes
    ADD CONSTRAINT workflow_processes_version_id_fkey FOREIGN KEY (version_id) REFERENCES public.workflow_versions(version_id);

ALTER TABLE ONLY public.workflow_versions
    ADD CONSTRAINT workflow_versions_activated_by_actor_id_fkey FOREIGN KEY (activated_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.workflow_versions
    ADD CONSTRAINT workflow_versions_created_by_actor_id_fkey FOREIGN KEY (created_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.workflow_versions
    ADD CONSTRAINT workflow_versions_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES public.workflows(workflow_id);

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_created_by_actor_id_fkey FOREIGN KEY (created_by_actor_id) REFERENCES public.actors(id);

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_lifecycle_id_fkey FOREIGN KEY (lifecycle_id) REFERENCES public.lifecycles(lifecycle_id);

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_set_id_fkey FOREIGN KEY (set_id) REFERENCES public.sets(set_id);

ALTER TABLE ONLY public.workflows
    ADD CONSTRAINT workflows_updated_by_actor_id_fkey FOREIGN KEY (updated_by_actor_id) REFERENCES public.actors(id);


INSERT INTO public.workflow_catalog VALUES ('py_arcgis_hub', 'ArcGIS Hub', 'Harvest metadata from ArcGIS Hub portals using their DCAT endpoints.', 'automated_retrieval');
INSERT INTO public.workflow_catalog VALUES ('py_oaipmh', 'OAI-PMH', 'Harvest metadata from OAI-PMH repositories using a configured metadata prefix and set, when applicable.', 'automated_retrieval');
INSERT INTO public.workflow_catalog VALUES ('curation_datasets', 'Dataset acquisition', 'Acquire datasets through direct download or provider submission and prepare them for the collection.', 'mediated_deposit');
INSERT INTO public.workflow_catalog VALUES ('curation_rest_service', 'Dataset generation from REST service', 'Retrieve or generate datasets from a REST service endpoint for curation and ingest.', 'manual_curation');
INSERT INTO public.workflow_catalog VALUES ('py_ckan', 'CKAN portal', 'Harvest metadata from CKAN portals using the CKAN API.', 'automated_retrieval');
INSERT INTO public.workflow_catalog VALUES ('py_mods', 'MODS metadata', 'Parse MODS XML files and transform the metadata into the Geoportal metadata profile.', 'mediated_deposit');
INSERT INTO public.workflow_catalog VALUES ('py_ogm_aardvark', 'OpenGeoMetadata repository', 'Harvest OGM Aardvark metadata from OpenGeoMetadata repositories.', 'automated_retrieval');
INSERT INTO public.workflow_catalog VALUES ('py_pasda', 'PASDA portal', 'Harvest PASDA metadata using the custom PASDA HTML-parsing workflow.', 'automated_retrieval');
INSERT INTO public.workflow_catalog VALUES ('py_pasda_metadata_directory', 'PASDA Metadata Directory', 'Retrieve and parse metadata files published through the PASDA Metadata Directory.', 'automated_retrieval');
INSERT INTO public.workflow_catalog VALUES ('py_socrata', 'Socrata portal', 'Harvest metadata from Socrata portals using their DCAT endpoints.', 'automated_retrieval');
INSERT INTO public.workflow_catalog VALUES ('template_children', 'Manual website and child records', 'Author a website record and its child records using the BTAA metadata template.', 'manual_curation');
INSERT INTO public.workflow_catalog VALUES ('template_csv', 'Submitted spreadsheet', 'Transform submitted spreadsheet metadata after review and minor cleanup using the standard template workflow.', 'mediated_deposit');
INSERT INTO public.workflow_catalog VALUES ('template_json', 'Submitted JSON', 'Transform submitted JSON files and perform minor cleanup', 'mediated_deposit');
INSERT INTO public.workflow_catalog VALUES ('template_website', 'Standalone websites', 'Author a standalone website record', 'manual_curation');
INSERT INTO public.workflow_process_types VALUES ('template_children', 'Template children', 'Create child metadata from a named template.');
INSERT INTO public.workflow_process_types VALUES ('template_csv', 'CSV template', 'Construct metadata using a named CSV template.');
INSERT INTO public.workflow_process_types VALUES ('template_website', 'Website template', 'Construct website metadata using a named template.');
INSERT INTO public.workflow_process_types VALUES ('template_json', 'JSON template', 'Construct metadata using a named JSON template.');
INSERT INTO public.workflow_process_types VALUES ('harvest', 'Harvest', 'Acquire source candidates for validation and review.');
INSERT INTO public.workflow_process_types VALUES ('transform', 'Transform', 'Apply a named, versioned metadata mapping.');
INSERT INTO public.workflow_process_types VALUES ('validate', 'Validate', 'Check metadata against the managed validation contract.');
INSERT INTO public.workflow_process_types VALUES ('review', 'Review', 'Review candidates before accepting managed changes.');
INSERT INTO public.workflow_process_types VALUES ('publish', 'Publish', 'Deliver accepted metadata through managed publication.');
