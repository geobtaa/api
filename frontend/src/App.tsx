import { Routes, Route, Navigate } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { Application } from '@hotwired/stimulus';
import { SearchPage } from './pages/SearchPage';
import { ResourceView } from './pages/ResourceView';
import { DebugProvider } from './context/DebugContext';
import { HomePage } from './pages/HomePage';
import { useSearchParams } from 'react-router';
import { BookmarkProvider } from './context/BookmarkContext';
import { BookmarksPage } from './pages/BookmarksPage';
import { FixturesTestPage } from './pages/FixturesTestPage';
import { ProviderPillsTestPage } from './pages/ProviderPillsTestPage';
import { MapPage } from './pages/MapPage';
import { TestPage } from './pages/TestPage';
import { NotFoundPage } from './pages/NotFoundPage';

// Import Leaflet CSS
import 'leaflet/dist/leaflet.css';

// Ensure Stimulus is available globally
const application = Application.start();
(window as any).Stimulus = application;

function App() {
  const [searchParams] = useSearchParams();
  const hasSearchParams = Array.from(searchParams.entries()).length > 0;

  // Build search string from URLSearchParams to avoid window.location issues
  const searchString = hasSearchParams ? `?${searchParams.toString()}` : '';

  return (
    <HelmetProvider>
      <BookmarkProvider>
        <DebugProvider>
          <Routes>
            {/* More specific paths first so /search matches before / */}
            <Route path="/search" element={<SearchPage />} />
            <Route path="/bookmarks" element={<BookmarksPage />} />
            <Route path="/resources/:id" element={<ResourceView />} />
            <Route
              path="/test/fixtures/providers"
              element={<ProviderPillsTestPage />}
            />
            <Route path="/test/fixtures" element={<FixturesTestPage />} />
            <Route path="/test" element={<TestPage />} />
            <Route path="/map" element={<MapPage />} />
            <Route
              path="/"
              element={
                hasSearchParams ? (
                  <Navigate to={`/search${searchString}`} replace />
                ) : (
                  <HomePage />
                )
              }
            />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </DebugProvider>
      </BookmarkProvider>
    </HelmetProvider>
  );
}

export default App;
