#!/usr/bin/env node

/**
 * Script to check if spatial facet aggregations contain data after reindexing
 * Usage: node check-spatial-facets.js [API_URL]
 * Example: node check-spatial-facets.js https://geo.btaa.org/api/v1/search
 */

const API_URL = process.argv[2] || 'https://geo.btaa.org/api/v1/search';

async function checkSpatialFacets() {
  console.log('🔍 Checking spatial facet aggregations...\n');
  console.log(`API URL: ${API_URL}\n`);

  const url = new URL(API_URL);
  url.searchParams.set('format', 'json');
  url.searchParams.set('search_field', 'all_fields');
  url.searchParams.set('q', '*'); // Search for everything
  url.searchParams.set('page', '1');
  url.searchParams.set('per_page', '1'); // We only need facets, not results

  try {
    console.log(`Fetching: ${url.toString()}\n`);
    
    const response = await fetch(url.toString(), {
      headers: {
        'Accept': 'application/vnd.api+json, application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    // Extract spatial facet
    const spatialFacet = data.included?.find(f => f.type === 'facet' && f.id === 'spatial_agg');

    console.log('═══════════════════════════════════════════════════════════\n');
    
    if (!spatialFacet) {
      console.log('❌ SPATIAL FACET NOT FOUND');
      console.log('\nThe API response does not include a "spatial_agg" facet.');
      console.log('This could mean:');
      console.log('  - The facet is not configured in the backend');
      console.log('  - No documents have spatial data indexed');
      console.log('  - The reindexing process has not completed\n');
      
      console.log('Available facets:');
      const availableFacets = data.included?.filter(f => f.type === 'facet') || [];
      if (availableFacets.length > 0) {
        availableFacets.forEach(f => {
          console.log(`  - ${f.id}: ${f.attributes.items?.length || 0} items`);
        });
      } else {
        console.log('  (none)\n');
      }
      return;
    }

    const items = spatialFacet.attributes.items || [];
    
    if (items.length === 0) {
      console.log('⚠️  SPATIAL FACET EXISTS BUT IS EMPTY');
      console.log('\nThe "spatial_agg" facet is configured but contains no data.');
      console.log('This means:');
      console.log('  - Documents may not have dct_spatial_sm field populated');
      console.log('  - The reindexing may not have processed spatial data yet\n');
      return;
    }

    console.log('✅ SPATIAL FACET DATA FOUND\n');
    console.log(`Total unique spatial values: ${items.length}\n`);
    
    // Calculate total documents with spatial data
    const totalDocs = items.reduce((sum, item) => sum + (item.attributes.hits || 0), 0);
    console.log(`Total documents with spatial data: ${totalDocs}\n`);
    
    // Show top 20 spatial values
    const sortedItems = [...items].sort((a, b) => b.attributes.hits - a.attributes.hits);
    const displayCount = Math.min(20, sortedItems.length);
    
    console.log(`Top ${displayCount} spatial values by document count:\n`);
    console.log('┌─────┬─────────────────────────────────────────────────┬───────┐');
    console.log('│ #   │ Place Name                                      │ Count │');
    console.log('├─────┼─────────────────────────────────────────────────┼───────┤');
    
    sortedItems.slice(0, displayCount).forEach((item, index) => {
      const rank = String(index + 1).padStart(3, ' ');
      const label = String(item.attributes.label || item.attributes.value).slice(0, 47).padEnd(47, ' ');
      const hits = String(item.attributes.hits).padStart(5, ' ');
      console.log(`│ ${rank} │ ${label} │ ${hits} │`);
    });
    
    console.log('└─────┴─────────────────────────────────────────────────┴───────┘\n');

    if (items.length > displayCount) {
      console.log(`... and ${items.length - displayCount} more spatial values\n`);
    }

    console.log('═══════════════════════════════════════════════════════════\n');
    console.log('✅ Spatial facet aggregations are working correctly!\n');

  } catch (error) {
    console.error('❌ ERROR:', error.message);
    console.error('\nFailed to check spatial facets. Please verify:');
    console.error('  - The API endpoint is accessible');
    console.error('  - The search service is running');
    console.error('  - Network connectivity\n');
    process.exit(1);
  }
}

// Run the check
checkSpatialFacets();


