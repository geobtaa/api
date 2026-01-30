import React from 'react';

// Simple card container for map sections with a title and optional subtitle
interface Props {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export function MapCard({ title, subtitle, children }: Props) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      <div className="p-4 border-b">
        <h3 className="font-semibold text-gray-900">{title}</h3>
        {subtitle && <p className="text-sm text-gray-600">{subtitle}</p>}
      </div>
      <div className="h-64">{children}</div>
    </div>
  );
}
