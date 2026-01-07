/**
 * Test script to verify API rate limiting
 * 
 * Without an API key, the API should allow 10 requests per minute.
 * The 11th request within a minute should return a 429 status code.
 */

const API_BASE_URL = process.env.VITE_API_BASE_URL || 'https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1';
const SEARCH_ENDPOINT = `${API_BASE_URL}/search`;

async function makeRequest(requestNumber) {
  const url = new URL(SEARCH_ENDPOINT);
  url.searchParams.set('format', 'json');
  url.searchParams.set('search_field', 'all_fields');
  url.searchParams.set('q', 'test');
  url.searchParams.set('page', '1');
  url.searchParams.set('per_page', '10');

  const startTime = Date.now();
  
  try {
    const response = await fetch(url.toString(), {
      headers: {
        'Accept': 'application/vnd.api+json, application/json',
      },
      mode: 'cors',
    });

    const endTime = Date.now();
    const duration = endTime - startTime;

    console.log(`Request ${requestNumber}: Status ${response.status} (${duration}ms)`);
    
    if (!response.ok) {
      const text = await response.text();
      try {
        const json = JSON.parse(text);
        console.log(`  Error details:`, json);
      } catch (e) {
        console.log(`  Error text:`, text.substring(0, 200));
      }
    }

    return {
      requestNumber,
      status: response.status,
      ok: response.ok,
      duration,
    };
  } catch (error) {
    const endTime = Date.now();
    const duration = endTime - startTime;
    console.error(`Request ${requestNumber} failed:`, error.message);
    return {
      requestNumber,
      status: null,
      ok: false,
      error: error.message,
      duration,
    };
  }
}

async function testRateLimiting() {
  console.log('Testing API rate limiting...');
  console.log(`API Endpoint: ${SEARCH_ENDPOINT}`);
  console.log('Making 11 requests without an API key...\n');

  const results = [];

  // Make 11 requests in quick succession
  for (let i = 1; i <= 11; i++) {
    const result = await makeRequest(i);
    results.push(result);
    
    // Small delay to avoid overwhelming, but keep requests within the same minute
    if (i < 11) {
      await new Promise(resolve => setTimeout(resolve, 100)); // 100ms delay
    }
  }

  console.log('\n=== Test Results ===');
  results.forEach(result => {
    const status = result.status || 'ERROR';
    const statusText = result.ok ? '✓' : (result.status === 429 ? '⚠️ (RATE LIMITED)' : '✗');
    console.log(`Request ${result.requestNumber}: ${status} ${statusText}`);
  });

  console.log('\n=== Analysis ===');
  const successfulRequests = results.filter(r => r.ok).length;
  const rateLimitedRequests = results.filter(r => r.status === 429).length;
  const errorRequests = results.filter(r => !r.ok && r.status !== 429).length;

  console.log(`Successful requests: ${successfulRequests}`);
  console.log(`Rate limited requests (429): ${rateLimitedRequests}`);
  console.log(`Other errors: ${errorRequests}`);

  // Check if the 11th request was rate limited
  const request11 = results.find(r => r.requestNumber === 11);
  if (request11?.status === 429) {
    console.log('\n✅ SUCCESS: The 11th request correctly returned 429 (Rate Limited)');
    return true;
  } else if (request11?.ok) {
    console.log('\n❌ FAILURE: The 11th request succeeded, but should have been rate limited (429)');
    return false;
  } else {
    console.log(`\n⚠️  UNEXPECTED: The 11th request returned status ${request11?.status || 'ERROR'}`);
    return false;
  }
}

// Run the test
testRateLimiting()
  .then(success => {
    process.exit(success ? 0 : 1);
  })
  .catch(error => {
    console.error('Test failed with error:', error);
    process.exit(1);
  });

