import { appUrl } from './api';
import btaaLogo from './assets/btaa-logo.png?inline';
import { showWorkManagement } from './config/features';
import { MaintenancePage } from './work/Maintenance';
import { WorkPage } from './work/Work';
import { TaskPage, NewTaskPage, NewPeriodPage } from './work/TaskEditor';
import { ui } from './ui/styles';
import { HomePage } from './home/HomePage';
import {
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
} from 'react-router';

import { NewResource } from './resources/NewResource';
import {
  BulkEditPage,
  BulkHistoryPage,
  BulkReviewPage,
} from './resources/BulkActions';
import { ResourceList, ResourceDetail } from './resources/ResourcePages';
import { ResourceSelectionPage } from './resources/ResourceSelections';
import { IntakeQueue } from './resources/IntakeQueue';
import { ResourceCsv } from './resources/ResourceCsv';

import { ResourceFixtures } from './ResourceFixtures';

import { MembershipPage } from './membership/MembershipPage';
import { JobPage, JobList } from './jobs/Jobs';
import { AccessPage } from './AccessPage';
import { SetWorkflowsPage } from './sets/SetWorkflows';
import { SetList } from './sets/SetBrowse';
import { SetPage } from './sets/SetEditor';
import { SourceList } from './sources/SourceBrowse';
import { SourcePage } from './sources/SourceEditor';

function ResourceImportRedirect() {
  const { search } = useLocation();
  return <Navigate replace to={{ pathname: '/resources/csv', search }} />;
}

function Layout() {
  return (
    <div className="min-h-screen bg-surface-muted">
      <a
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-3 focus:text-primary focus:shadow-lg"
        href="#main-content"
      >
        Skip to content
      </a>
      <header className="relative z-30 flex flex-wrap items-center justify-between gap-4 bg-primary px-4 py-3 text-white shadow-sm sm:px-6 lg:sticky lg:top-0 lg:px-8 [&_:focus-visible]:outline-white">
        <Link
          className="inline-flex shrink-0 items-center gap-3 text-white no-underline [&_img]:h-12 [&_img]:w-auto [&_strong]:text-2xl [&_strong]:font-medium [&_small]:text-xs"
          to="/"
          aria-label="GEOMG Admin home"
        >
          <img
            src={btaaLogo}
            alt="Big Ten Academic Alliance"
            width="651"
            height="383"
          />
          <span className="flex min-h-11 flex-col justify-center border-l border-white/60 pl-3 font-brand">
            <strong>GEOMG</strong>
            <small>Metadata administration</small>
          </span>
        </Link>
        <nav className="flex flex-wrap gap-1" aria-label="Primary navigation">
          <NavLink className={ui.navLink} to="/">
            Home
          </NavLink>
          <NavLink className={ui.navLink} to="/resources">
            Resources
          </NavLink>
          <NavLink className={ui.navLink} to="/sources">
            Sources
          </NavLink>
          <NavLink className={ui.navLink} to="/sets">
            Sets
          </NavLink>
          {showWorkManagement && (
            <>
              <NavLink className={ui.navLink} to="/work">
                Work
              </NavLink>
              <NavLink className={ui.navLink} to="/jobs">
                Jobs
              </NavLink>
            </>
          )}
        </nav>
        <nav
          className="flex flex-wrap gap-1 lg:border-l lg:border-white/30 lg:pl-4"
          aria-label="Account and system"
        >
          <NavLink className={ui.navLink} to="/access">
            Access
          </NavLink>
          <NavLink className={ui.navLink} to="/system">
            System
          </NavLink>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/resource-fixtures" element={<ResourceFixtures />} />
        <Route path="/resources" element={<ResourceList />} />
        <Route path="/resources/new" element={<NewResource />} />
        <Route
          path="/resources/selections/:selectionId/bulk-edit"
          element={<BulkEditPage />}
        />
        <Route path="/resource-bulk-actions" element={<BulkHistoryPage />} />
        <Route
          path="/resource-bulk-actions/:actionId"
          element={<BulkReviewPage />}
        />
        <Route path="/sets" element={<SetList />} />
        <Route path="/sets/new" element={<SetPage mode="create" />} />
        <Route path="/sets/:setId/workflows" element={<SetWorkflowsPage />} />
        <Route path="/sets/:setId" element={<SetPage />} />
        <Route path="/sets/:setId/edit" element={<SetPage mode="edit" />} />
        <Route path="/sources" element={<SourceList />} />
        <Route path="/sources/new" element={<SourcePage mode="create" />} />
        <Route path="/sources/:sourceId" element={<SourcePage />} />
        <Route
          path="/sources/:sourceId/edit"
          element={<SourcePage mode="edit" />}
        />
        <Route
          path="/resources/selections/:selectionId"
          element={<ResourceSelectionPage />}
        />
        <Route
          path="/resources/csv/distributions"
          element={<ResourceCsv key="distributions" entity="distributions" />}
        />
        <Route
          path="/sources/csv/import"
          element={<ResourceCsv key="sources" entity="sources" />}
        />
        <Route
          path="/sets/csv/import"
          element={<ResourceCsv key="sets" entity="sets" />}
        />
        <Route
          path="/resources/csv"
          element={<ResourceCsv key="resources" />}
        />
        <Route
          path="/resources/csv/intake/:batchId?"
          element={<IntakeQueue />}
        />
        <Route path="/resources/import" element={<ResourceImportRedirect />} />
        <Route
          path="/resources/:resourceId/set"
          element={<MembershipPage mode="association" />}
        />
        <Route
          path="/sets/:setId/representative"
          element={<MembershipPage mode="representative" />}
        />
        <Route path="/resources/:resourceId" element={<ResourceDetail />} />
        {showWorkManagement && (
          <>
            <Route
              path="/sets/:setId/maintenance"
              element={<MaintenancePage />}
            />
            <Route path="/work" element={<WorkPage />} />
            <Route path="/work/periods/new" element={<NewPeriodPage />} />
            <Route path="/tasks/new" element={<NewTaskPage />} />
            <Route path="/tasks/:taskId" element={<TaskPage />} />
            <Route path="/jobs" element={<JobList />} />
            <Route path="/jobs/:jobId" element={<JobPage />} />
          </>
        )}
        <Route path="/access" element={<AccessPage />} />
        <Route path="/system" element={<SystemPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </div>
  );
}

function SystemPage() {
  return (
    <main id="main-content" className={ui.page}>
      <p className={ui.kicker}>Platform</p>
      <h1>System endpoints</h1>
      <p className="max-w-2xl text-base leading-7 text-text-secondary">
        These API checks separate process liveness from database readiness.
      </p>
      <a className={ui.secondary} href={appUrl('/api/docs')}>
        Open API docs
      </a>
      <dl className={ui.definitionList}>
        <div>
          <dt>/api/v1/health</dt>
          <dd>Confirms that the FastAPI process is accepting requests.</dd>
        </div>
        <div>
          <dt>/api/v1/ready</dt>
          <dd>Confirms that the application can reach PostgreSQL.</dd>
        </div>
      </dl>
    </main>
  );
}

function NotFoundPage() {
  return (
    <main id="main-content" className={ui.page}>
      <p className={ui.kicker}>404</p>
      <h1>Page not found</h1>
      <Link className={ui.primary} to="/">
        Return home
      </Link>
    </main>
  );
}

export default Layout;
