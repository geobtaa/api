# API Keys and Service Tiers: A Guide for Librarians

## Introduction

The BTAA Geospatial API now uses **API keys** and **service tiers** to ensure fair access to our geospatial data for all users. This system helps us provide better service while preventing any single user from overwhelming the system with too many requests.

Think of it like a library card: you register to get access, and different types of users (students, faculty, community members) have different borrowing limits that match their needs.

## What is an API Key?

An **API key** is like a password that identifies who is making a request to our API. It's a long string of letters and numbers (like `a1b2c3d4-e5f6-7890-abcd-ef1234567890`) that uniquely identifies each user or application.

### Why Do We Use API Keys?

1. **Fair Access**: API keys let us ensure that everyone gets their fair share of the service, preventing one user from accidentally (or intentionally) making so many requests that others can't use the system.

2. **Usage Tracking**: We can see how different users and applications are using the API, which helps us improve the service and understand what features are most valuable.

3. **Better Service**: By tracking usage, we can identify and optimize the most popular endpoints, making the API faster for everyone.

4. **Security**: API keys help us prevent abuse and quickly revoke access if needed, while keeping legitimate users running smoothly.

## What are Service Tiers?

A **service tier** determines how many requests per minute a user can make to the API. Different types of users have different needs, so we've created six tiers:

### The Six Service Tiers

1. **BTAA Primary** (`btaa_primary`)
   - **Who**: The main BTAA Geoportal frontend application
   - **Limit**: Unlimited requests
   - **Why**: This is our primary public-facing application, so it needs priority access

2. **BTAA Secondary** (`btaa_secondary`)
   - **Who**: Other official BTAA applications and services
   - **Limit**: Unlimited requests
   - **Why**: These are our internal applications that support the BTAA mission

3. **BTAA Member Primary** (`btaa_member_primary`)
   - **Who**: Primary applications from Big Ten member universities
   - **Limit**: 1,000 requests per minute
   - **Why**: Member universities are core partners and often build applications that integrate with our data

4. **BTAA Member Affiliated** (`btaa_member_affiliated`)
   - **Who**: Affiliated applications from Big Ten member universities (secondary projects, research applications)
   - **Limit**: 500 requests per minute
   - **Why**: These applications are important but may not need the same level of access as primary applications

5. **General Registered** (`general_registered`)
   - **Who**: External users who have registered and requested an API key
   - **Limit**: 100 requests per minute
   - **Why**: This provides good access for legitimate external users while preventing abuse

6. **Anonymous** (`anonymous`)
   - **Who**: Anyone using the API without an API key
   - **Limit**: 10 requests per minute
   - **Why**: This allows casual browsing and testing, but encourages registration for serious use

### Understanding Rate Limits

A **rate limit** is the maximum number of requests you can make in one minute. For example, if you have a limit of 100 requests per minute:

- You can make 100 requests in any 60-second window
- If you try to make a 101st request within that minute, you'll receive an error
- After the minute expires, you get a fresh set of 100 requests
- The limit resets every minute, so over an hour you could make up to 6,000 requests (100 × 60)

This is similar to how some library databases limit how many articles you can download per hour to ensure fair access for all users.

Crawler metadata routes (`/robots.txt`, `/sitemap.xml`, and `/sitemaps/*.xml`)
bypass API throttling so search engines can discover public pages without
consuming anonymous API quota.

## How to Use an API Key

If you're a developer or librarian setting up an application to use our API, you'll need to include the API key with each request. There are three ways to do this:

### Method 1: X-API-Key Header (Recommended)
Add the API key as a header in your request:
```
X-API-Key: your-api-key-here
```

### Method 2: Authorization Header
Use the standard Bearer token format:
```
Authorization: Bearer your-api-key-here
```

### Method 3: Query Parameter
Include the API key as a parameter in the URL:
```
https://api.example.com/api/v1/search?q=roads&api_key=your-api-key-here
```

**Note**: The header methods (1 and 2) are preferred because they don't expose the API key in URLs, which can be logged or shared accidentally.

### What Happens Without an API Key?

If you make a request without an API key (or with an invalid key), the API will still work, but you'll be automatically assigned to the **Anonymous** tier with a limit of 10 requests per minute. This is fine for casual browsing or testing, but if you need more access, you should register for an API key.

## Requesting an API Key

### For External Users

External users (non-BTAA members) should:

1. Contact the BTAA Geoportal team to request an API key
2. Provide information about:
   - Your name and organization
   - What you plan to use the API for
   - Expected usage volume
3. You'll be assigned to the **General Registered** tier (100 requests/minute) by default

### For BTAA Member Universities

BTAA member universities can request API keys for their applications. Contact the BTAA Geoportal team with:

1. Information about your application
2. Whether it's a primary institutional application or an affiliated project
3. Expected usage patterns

You'll be assigned to either the **BTAA Member Primary** (1,000 requests/minute) or **BTAA Member Affiliated** (500 requests/minute) tier, depending on your needs.

### For BTAA Applications

Internal BTAA applications are automatically assigned to the **BTAA Primary** or **BTAA Secondary** tier with unlimited access.

## What Happens When You Exceed Your Rate Limit?

If you exceed your rate limit (make too many requests too quickly), the API will respond with:

- **HTTP Status Code**: 429 (Too Many Requests)
- **Response Body**: An error message explaining that you've exceeded your limit
- **Headers**: Additional information including:
  - `X-RateLimit-Limit`: Your tier's request limit
  - `X-RateLimit-Remaining`: How many requests you have left (will be 0)
  - `X-RateLimit-Reset`: When the limit resets (as a Unix timestamp)
  - `Retry-After`: How many seconds to wait before trying again

Your application should wait until the limit resets (usually just a few seconds) before making more requests. Most programming libraries can handle this automatically.

## Understanding the Rate Limit Headers

Every API response includes headers that tell you about your rate limit status:

- `X-RateLimit-Limit`: The maximum number of requests per minute for your tier
- `X-RateLimit-Remaining`: How many requests you have left in the current minute
- `X-RateLimit-Reset`: When your limit will reset (Unix timestamp)

For unlimited tiers (BTAA Primary and Secondary), these headers will show "unlimited" or -1.

## Usage Analytics and Privacy

All API requests are logged to help us:

- Understand how the API is being used
- Identify popular features and optimize performance
- Detect and prevent abuse
- Plan for future improvements

The logs include:
- The endpoint accessed
- The service tier used
- The API key ID (not the actual key)
- Request timing and response codes
- IP address and user agent (browser/client information)
- Referrer information (where the request came from)

**Privacy**: The actual API keys are never stored in logs—only hashed identifiers. Personal information is handled according to standard privacy practices.

## Managing API Keys (For Administrators)

If you're an administrator managing API keys for the BTAA Geoportal, you can use the admin API endpoints (protected by HTTP Basic authentication) to:

- **Create new API keys**: Assign keys to users with appropriate tiers
- **List existing keys**: See all active API keys and their tiers
- **Update keys**: Change a key's tier, activate/deactivate it, or update metadata
- **Revoke keys**: Deactivate a key if it's no longer needed or has been compromised
- **View tiers**: See all available service tiers and their limits

The admin endpoints are only accessible to authorized administrators and should never be exposed publicly.

## Frequently Asked Questions

### Q: Do I need an API key to use the API?

**A**: No, but you'll be limited to 10 requests per minute. For serious use, we recommend registering for an API key.

### Q: Can I share my API key with others?

**A**: No, API keys are like passwords—they're personal to you or your application. Sharing keys can lead to:
- Your key being revoked if it's abused
- Difficulty tracking usage for your application
- Security risks

Each user or application should have their own API key.

### Q: What if I need more than 100 requests per minute?

**A**: Contact the BTAA Geoportal team to discuss your needs. We can work with you to find an appropriate tier or make accommodations for legitimate high-volume use cases.

### Q: What happens if I lose my API key?

**A**: Contact the BTAA Geoportal team. We can deactivate the old key and issue you a new one.

### Q: How do I know which tier I'm in?

**A**: Check the `X-RateLimit-Limit` header in any API response. You can also contact the BTAA Geoportal team to confirm your tier assignment.

### Q: Can I upgrade or downgrade my tier?

**A**: Yes, contact the BTAA Geoportal team to discuss changing your tier based on your usage needs.

### Q: Why are there different tiers?

**A**: Different users have different needs. A researcher testing a small script needs less access than a member university's main geospatial application. Tiers help us ensure everyone gets appropriate access while maintaining system stability.

### Q: What if I'm making requests from multiple applications?

**A**: Each application should have its own API key. This helps us:
- Track usage accurately
- Manage access independently
- Respond to issues with specific applications

### Q: Are API keys secure?

**A**: Yes. API keys are stored using industry-standard hashing (SHA-256), similar to how passwords are stored. The actual key is only shown once when it's created—after that, only hashed versions are stored. Always treat your API key like a password and keep it secure.

## Summary

- **API keys** identify who is using the API and enable fair access controls
- **Service tiers** determine how many requests per minute you can make
- **Rate limits** prevent any single user from overwhelming the system
- **Six tiers** serve different user types, from unlimited (BTAA applications) to 10 requests/minute (anonymous users)
- **Usage logging** helps us improve the service and understand how it's being used
- **Admin tools** allow authorized staff to manage keys and tiers

This system ensures that the BTAA Geospatial API remains fast, reliable, and accessible to all users while supporting both casual browsing and high-volume institutional applications.

For questions or to request an API key, please contact the BTAA Geoportal team.
