import React from 'react';
import { Helmet } from 'react-helmet-async';
import { useLocation } from 'react-router';

interface SeoProps {
    title: string;
    description?: string;
    image?: string;
    url?: string;
    type?: 'website' | 'article' | 'book';
}

export function Seo({
    title,
    description = "The Big Ten Academic Alliance Geoportal provides discoverability and facilitates access to geospatial resources.",
    image = "/thumbnail_placeholder.png", // We should check if we have a better default
    url,
    type = 'website'
}: SeoProps) {
    const location = useLocation();
    const isClient = typeof window !== 'undefined';
    const siteTitle = "Big Ten Academic Alliance Geoportal";
    const fullTitle = title === siteTitle ? siteTitle : `${title} - ${siteTitle}`;
    
    // Get URL: use provided url (from loader), or fall back to constructing from location
    const currentUrl = url || (isClient 
        ? window.location.href 
        : `${location.pathname}${location.search}`);

    // Ensure image is absolute URL
    // If server-side and no origin, we might want a base URL env var, but for now empty string or guarded usage
    const origin = isClient ? window.location.origin : '';
    const absoluteImage = image?.startsWith('http')
        ? image
        : `${origin}${image?.startsWith('/') ? '' : '/'}${image}`;

    return (
        <Helmet>
            {/* Standard Metadata */}
            <title>{fullTitle}</title>
            <meta name="description" content={description} />

            {/* Open Graph / Facebook */}
            <meta property="og:type" content={type} />
            <meta property="og:url" content={currentUrl} />
            <meta property="og:title" content={fullTitle} />
            <meta property="og:description" content={description} />
            <meta property="og:image" content={absoluteImage} />
            <meta property="og:site_name" content={siteTitle} />

            {/* Twitter */}
            <meta name="twitter:card" content="summary_large_image" />
            <meta name="twitter:url" content={currentUrl} />
            <meta name="twitter:title" content={fullTitle} />
            <meta name="twitter:description" content={description} />
            <meta name="twitter:image" content={absoluteImage} />
        </Helmet>
    );
}
