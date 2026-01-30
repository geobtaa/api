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

const DEFAULT_ICON_CLASS = 'w-24 h-24 text-gray-400';

export function getResourceIcon(
  resourceClass: string | undefined,
  options?: { className?: string }
): React.ReactNode {
  const cn = options?.className ?? DEFAULT_ICON_CLASS;
  switch (resourceClass?.toLowerCase()) {
    case 'datasets':
      return <Database className={cn} />;
    case 'maps':
      return <Map className={cn} />;
    case 'web services':
      return <Globe className={cn} />;
    case 'collections':
      return <Library className={cn} />;
    case 'imagery':
      return <Image className={cn} />;
    case 'websites':
      return <Globe2 className={cn} />;
    case 'other':
      return <Folder className={cn} />;
    default:
      return <Folder className={cn} />;
  }
}
