import React from 'react';
import {
  Database,
  Map,
  Globe,
  Library,
  Image,
  Folder,
  Globe2,
} from 'lucide-react';

export function getResourceIcon(
  resourceClass: string | undefined
): React.ReactNode {
  switch (resourceClass?.toLowerCase()) {
    case 'datasets':
      return <Database className="w-24 h-24 text-gray-400" />;
    case 'maps':
      return <Map className="w-24 h-24 text-gray-400" />;
    case 'web services':
      return <Globe className="w-24 h-24 text-gray-400" />;
    case 'collections':
      return <Library className="w-24 h-24 text-gray-400" />;
    case 'imagery':
      return <Image className="w-24 h-24 text-gray-400" />;
    case 'websites':
      return <Globe2 className="w-24 h-24 text-gray-400" />;
    default:
      return <Folder className="w-24 h-24 text-gray-400" />;
  }
}
