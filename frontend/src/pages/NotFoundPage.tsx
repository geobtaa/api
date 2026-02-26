import { Link } from 'react-router';
import { Seo } from '../components/Seo';

export function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <Seo title="Page Not Found" />
      <div className="max-w-md w-full text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Page not found
        </h1>
        <p className="text-gray-600 mb-8">
          The page you’re looking for doesn’t exist or has been moved.
        </p>
        <Link
          to="/"
          className="inline-block px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700"
        >
          Go to homepage
        </Link>
      </div>
    </div>
  );
}
