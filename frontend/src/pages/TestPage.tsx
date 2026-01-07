export function TestPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Test Page - React 19 Upgrade
        </h1>
        <p className="text-gray-600">
          This is a simple test page to verify React 19 is working correctly.
        </p>
        <div className="mt-4 p-4 bg-blue-100 rounded-lg">
          <p className="text-blue-800">
            If you can see this, React 19 is working!
          </p>
        </div>
      </div>
    </div>
  );
}
