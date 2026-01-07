import type { LoaderFunctionArgs } from "react-router";
import { useLoaderData } from "react-router";
import { ResourceView } from "../../src/pages/ResourceView";
import { serverFetchJson } from "../lib/server-api";
import type { GeoDocumentDetails } from "../../src/types/api";

/**
 * Loader function that runs server-side to fetch resource details.
 * For now, ResourceView fetches its own data, but we can pre-fetch here
 * and pass it as props in the future.
 */
export async function loader({ params }: LoaderFunctionArgs) {
  const { id } = params;

  if (!id) {
    throw new Response("Resource ID is required", { status: 400 });
  }

  try {
    const resource = await serverFetchJson<{ data: GeoDocumentDetails }>(
      `/resources/${id}?format=json`
    );

    return { resource: resource.data };
  } catch (error) {
    console.error("Resource loader error:", error);
    if (error instanceof Response && error.status === 404) {
      throw error;
    }
    // Allow ResourceView to handle its own errors for now
    return { resource: null };
  }
}

/**
 * Resource detail page.
 * ResourceView currently fetches its own data, but loader data is available
 * via useLoaderData() if we want to pre-populate in the future.
 */
export default function Resource() {
  const { resource } = useLoaderData() as { resource: GeoDocumentDetails | null };
  // Prefer loader data (server-side) to avoid duplicate client fetches.
  return <ResourceView prefetchedResource={resource ?? undefined} />;
}
