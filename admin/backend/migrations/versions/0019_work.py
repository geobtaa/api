"""Durable Set work occurrences, maintenance rules and reporting periods."""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE set_maintenance (
	set_id VARCHAR(128) NOT NULL,
	work_type VARCHAR(16) NOT NULL,
	interval VARCHAR(16) NOT NULL,
    next_due_on DATE,
	enabled BOOLEAN DEFAULT 'true' NOT NULL,
	assignee_id UUID,
	lock_version INTEGER DEFAULT '1' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (set_id, work_type),
	CONSTRAINT maintenance_work_type CHECK (work_type IN ('review', 'ingest')),
	CONSTRAINT maintenance_interval CHECK (interval ~ '^P[1-9][0-9]{0,2}[DWMY]$|^P1000[DWMY]$'),
	CONSTRAINT maintenance_version CHECK (lock_version > 0),
	FOREIGN KEY(set_id) REFERENCES sets (set_id),
	FOREIGN KEY(assignee_id) REFERENCES actors (id)
)""")
    op.execute("""CREATE TABLE work_tasks (
	task_id UUID NOT NULL,
	set_id VARCHAR(128) NOT NULL,
	work_type VARCHAR(16) NOT NULL,
	title VARCHAR(250) NOT NULL,
	description TEXT DEFAULT '' NOT NULL,
	status VARCHAR(16) DEFAULT 'open' NOT NULL,
	due_on DATE NOT NULL,
	planned_on DATE,
	assignee_id UUID,
	recurring BOOLEAN DEFAULT 'false' NOT NULL,
	predecessor_id UUID,
	lock_version INTEGER DEFAULT '1' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	created_by_id UUID NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	completion_recorded_at TIMESTAMP WITH TIME ZONE,
	completed_by_id UUID,
	completion_summary TEXT,
	evidence JSONB DEFAULT '[]' NOT NULL,
	processed_count INTEGER DEFAULT '0' NOT NULL,
	changed_count INTEGER DEFAULT '0' NOT NULL,
	PRIMARY KEY (task_id),
	CONSTRAINT task_work_type CHECK (work_type IN ('review','ingest','other')),
	CONSTRAINT task_status CHECK (status IN ('open','in_progress','blocked',
'completed','cancelled')),
	CONSTRAINT task_title CHECK (length(btrim(title)) BETWEEN 1 AND 250),
	CONSTRAINT task_version CHECK (lock_version > 0),
	CONSTRAINT task_recurrence_type CHECK (NOT recurring OR work_type IN ('review','ingest')),
        CONSTRAINT task_counts CHECK (processed_count >= 0 AND changed_count BETWEEN 0 AND
processed_count),
        CONSTRAINT task_completion CHECK ((status = 'completed' AND completed_at IS NOT NULL AND
completion_recorded_at IS NOT NULL AND completed_by_id IS NOT NULL AND
length(btrim(completion_summary)) > 0 AND completed_at <= completion_recorded_at) OR (status <>
'completed' AND completed_at IS NULL AND completion_recorded_at IS NULL AND completed_by_id IS
NULL AND completion_summary IS NULL)),
	FOREIGN KEY(set_id) REFERENCES sets (set_id),
	FOREIGN KEY(assignee_id) REFERENCES actors (id),
	UNIQUE (predecessor_id),
	FOREIGN KEY(predecessor_id) REFERENCES work_tasks (task_id),
	FOREIGN KEY(created_by_id) REFERENCES actors (id),
	FOREIGN KEY(completed_by_id) REFERENCES actors (id)
)""")
    op.execute(
        """CREATE UNIQUE INDEX one_open_recurrence ON work_tasks (set_id, work_type)
WHERE recurring AND status IN ('open', 'in_progress', 'blocked')"""
    )
    op.execute("""CREATE INDEX tasks_assignee ON work_tasks (assignee_id, status, due_on)""")
    op.execute("""CREATE INDEX tasks_completed ON work_tasks (completed_at, task_id)""")
    op.execute("""CREATE INDEX tasks_queue ON work_tasks (status, due_on, task_id)""")
    op.execute("""CREATE INDEX tasks_set_due ON work_tasks (set_id, due_on)""")
    op.execute("""CREATE TABLE work_task_events (
	event_id UUID NOT NULL,
	task_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	actor_name TEXT NOT NULL,
	action VARCHAR(32) NOT NULL,
	occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	details JSONB NOT NULL,
	PRIMARY KEY (event_id),
	FOREIGN KEY(task_id) REFERENCES work_tasks (task_id),
	FOREIGN KEY(actor_id) REFERENCES actors (id)
)""")
    op.execute(
        """CREATE INDEX task_event_time ON work_task_events (task_id, recorded_at, event_id)"""
    )
    op.execute("""CREATE TABLE work_periods (
	period_id UUID NOT NULL,
	name VARCHAR(120) NOT NULL,
	starts_on DATE NOT NULL,
	ends_on DATE NOT NULL,
	lock_version INTEGER DEFAULT '1' NOT NULL,
	created_by_id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (period_id),
	CONSTRAINT period_range CHECK (ends_on >= starts_on),
	CONSTRAINT period_name CHECK (length(btrim(name)) > 0),
	CONSTRAINT period_version CHECK (lock_version > 0),
	UNIQUE (name),
	FOREIGN KEY(created_by_id) REFERENCES actors (id)
)""")
    op.execute("""CREATE FUNCTION work_event_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Work event history is immutable'; END $$""")
    op.execute("""CREATE TRIGGER work_event_immutable BEFORE UPDATE OR DELETE ON work_task_events
FOR EACH ROW EXECUTE FUNCTION work_event_immutable()""")
    op.execute("""CREATE FUNCTION work_task_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
END $$""")
    op.execute("""CREATE TRIGGER work_task_guard BEFORE UPDATE ON work_tasks
FOR EACH ROW EXECUTE FUNCTION work_task_guard()""")


def downgrade():
    op.execute("""DO $$ BEGIN
IF EXISTS(SELECT 1 FROM work_tasks) OR EXISTS(SELECT 1 FROM set_maintenance)
 OR EXISTS(SELECT 1 FROM work_periods) THEN
 RAISE EXCEPTION 'Refuse to discard work records; export and reconcile before downgrade';
END IF; END $$""")
    op.execute("DROP TABLE work_task_events, work_tasks, set_maintenance, work_periods")
    op.execute("DROP FUNCTION work_task_guard(), work_event_immutable()")
