import { ExternalLink, LockKeyhole, University } from 'lucide-react';
import { scheduleAnalyticsBatch } from '../../services/analytics';
import { getProviderIconSlug } from '../../utils/providerIcons';

export interface LicensedAccessItem {
  institution_code: string;
  institution_name?: string | null;
  access_url: string;
  legacy_friendlier_id?: string | null;
}

interface LicensedAccessesTableProps {
  licensedAccesses: LicensedAccessItem[];
  resourceId?: string;
  searchId?: string;
}

function InstitutionIcon({ name }: { name: string }) {
  const iconSlug = getProviderIconSlug(name);

  if (iconSlug) {
    return (
      <span className="flex h-8 w-8 shrink-0 items-center justify-center border border-gray-200 bg-white">
        <img
          src={`/icons/${iconSlug}.svg`}
          alt=""
          aria-hidden="true"
          className="h-5 w-5 object-contain"
        />
      </span>
    );
  }

  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center border border-gray-200 bg-gray-50 text-gray-500">
      <University className="h-4 w-4" aria-hidden="true" />
    </span>
  );
}

export function LicensedAccessesTable({
  licensedAccesses,
  resourceId,
  searchId,
}: LicensedAccessesTableProps) {
  if (!licensedAccesses || licensedAccesses.length === 0) return null;

  const trackAccessClick = (access: LicensedAccessItem, label: string) => {
    scheduleAnalyticsBatch({
      events: [
        {
          event_type: 'licensed_access_click',
          search_id: searchId,
          resource_id: resourceId,
          label,
          destination_url: access.access_url,
          source_component: 'LicensedAccessesTable',
          properties: {
            institution_code: access.institution_code,
            legacy_friendlier_id: access.legacy_friendlier_id,
          },
        },
      ],
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <LockKeyhole className="h-5 w-5 text-gray-500" aria-hidden="true" />
          <h2 className="text-lg font-semibold text-gray-900">
            Licensed Resource
          </h2>
        </div>
      </div>
      <div className="divide-y divide-gray-200">
        {licensedAccesses.map((access, index) => {
          const label =
            access.institution_name?.trim() ||
            access.institution_code?.trim() ||
            'Institutional access';

          return (
            <a
              key={`${access.institution_code}-${access.access_url}-${index}`}
              href={access.access_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackAccessClick(access, label)}
              className="flex items-center gap-3 px-6 py-4 hover:bg-gray-50 group"
            >
              <InstitutionIcon name={label} />
              <span className="min-w-0 flex-1 text-sm font-medium text-gray-900 break-words group-hover:text-blue-600">
                {label}
              </span>
              <ExternalLink
                className="h-4 w-4 shrink-0 text-gray-400 group-hover:text-blue-500"
                aria-hidden="true"
              />
            </a>
          );
        })}
      </div>
    </div>
  );
}
