/**
 * Test script to verify API rate limiting with an API key
 * 
 * With an API key, users should be able to make more than 10 requests per minute
 * (depending on their service tier: 100, 500, 1000, or unlimited requests/minute).
 * This test verifies that the 11th request succeeds when using an API key.
 */

const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
const SEARCH_ENDPOINT = `${API_BASE_URL}/search`;
const API_KEY = '6477d94c-4763-4c45-aef2-80b9fe5103e0';

async function makeRequest(requestNumber, useApiKey = true) {
  const url = new URL(SEARCH_ENDPOINT);
  url.searchParams.set('format', 'json');
  url.searchParams.set('search_field', 'all_fields');
  url.searchParams.set('q', 'test');
  url.searchParams.set('page', '1');
  url.searchParams.set('per_page', '10');

  const headers = {
    'Accept': 'application/vnd.api+json, application/json',
  };

  // Add API key via X-API-Key header (recommended method)
  if (useApiKey) {
    headers['X-API-Key'] = API_KEY;
  }

  const startTime = Date.now();
  
  try {
    const response = await fetch(url.toString(), {
      headers,
      mode: 'cors',
    });

    const endTime = Date.now();
    const duration = endTime - startTime;

    // Extract rate limit headers
    const rateLimitLimit = response.headers.get('X-RateLimit-Limit');
    const rateLimitRemaining = response.headers.get('X-RateLimit-Remaining');
    const rateLimitReset = response.headers.get('X-RateLimit-Reset');

    console.log(`Request ${requestNumber}: Status ${response.status} (${duration}ms)`);
    if (rateLimitLimit) {
      console.log(`  Rate Limit: ${rateLimitLimit}/min, Remaining: ${rateLimitRemaining}, Reset: ${rateLimitReset}`);
    }
    
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
      rateLimitLimit,
      rateLimitRemaining,
      rateLimitReset,
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

async function testRateLimitingWithKey() {
  console.log('Testing API rate limiting WITH API key...');
  console.log(`API Endpoint: ${SEARCH_ENDPOINT}`);
  console.log(`API Key: ${API_KEY.substring(0, 8)}...${API_KEY.substring(API_KEY.length - 8)}`);
  console.log('Making 11 requests with API key...\n');

  const results = [];

  // Make 11 requests in quick succession
  for (let i = 1; i <= 11; i++) {
    const result = await makeRequest(i, true);
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
    const limitInfo = result.rateLimitLimit ? ` [Limit: ${result.rateLimitLimit}, Remaining: ${result.rateLimitRemaining}]` : '';
    console.log(`Request ${result.requestNumber}: ${status} ${statusText}${limitInfo}`);
  });

  console.log('\n=== Analysis ===');
  const successfulRequests = results.filter(r => r.ok).length;
  const rateLimitedRequests = results.filter(r => r.status === 429).length;
  const errorRequests = results.filter(r => !r.ok && r.status !== 429).length;

  console.log(`Successful requests: ${successfulRequests}`);
  console.log(`Rate limited requests (429): ${rateLimitedRequests}`);
  console.log(`Other errors: ${errorRequests}`);

  // Display service tier information from first successful request
  const firstSuccess = results.find(r => r.ok && r.rateLimitLimit);
  if (firstSuccess) {
    console.log(`\nService Tier Information:`);
    console.log(`  Rate Limit: ${firstSuccess.rateLimitLimit} requests/minute`);
    console.log(`  (This indicates your tier allows more than 10 requests/minute)`);
  }

  // Check if all 11 requests succeeded (which should happen with an API key)
  const request11 = results.find(r => r.requestNumber === 11);
  if (request11?.ok) {
    console.log('\n✅ SUCCESS: The 11th request succeeded with API key (rate limiting bypassed for higher tier)');
    if (request11.rateLimitLimit && parseInt(request11.rateLimitLimit) > 10) {
      console.log(`   Your API key is assigned to a tier with ${request11.rateLimitLimit} requests/minute limit`);
    }
    return true;
  } else if (request11?.status === 429) {
    console.log('\n⚠️  WARNING: The 11th request was rate limited even with API key');
    console.log('   This might indicate the API key tier limit is 10 or less, or there was an issue');
    return false;
  } else {
    console.log(`\n❌ FAILURE: The 11th request returned status ${request11?.status || 'ERROR'}`);
    return false;
  }
}

// Run the test
testRateLimitingWithKey()
  .then(success => {
    process.exit(success ? 0 : 1);
  })
  .catch(error => {
    console.error('Test failed with error:', error);
    process.exit(1);
  });

