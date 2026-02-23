# External API Feedback Question Set

Use this short set to get practical, implementation-level feedback from external library application developers.

## Discussion Questions (7 total)

1. **Metadata boundaries (`ogm` vs `b1g`)**  
   Where are boundaries still unclear in real integrations, and what concrete metadata ownership model would reduce ambiguity?

2. **Onboarding friction**  
   If your team started integrating tomorrow, what part of docs, auth, or endpoint discovery would slow you down first?

3. **API consistency**  
   Which request/response patterns (naming, filtering, pagination, field shapes) feel inconsistent across endpoints?

4. **Search relevance and field usefulness**  
   Do search results include the right fields and ranking behavior for your discovery and display use cases?

5. **Error handling quality**  
   Are status codes and error payloads actionable enough to diagnose issues quickly and build reliable user-facing fallbacks?

6. **Versioning and change management**  
   What deprecation timeline and compatibility guarantees would you require to adopt the API with confidence?

7. **Top missing capability**  
   What is the single most important missing capability right now (endpoint, filter, bulk operation, or event/webhook)?

## Suggested Order (30-45 minute format)

1. Start with real integration context (Question 2).  
2. Move to data model boundaries (Question 1).  
3. Validate day-to-day API shape and behavior (Questions 3-5).  
4. Confirm trust and lifecycle expectations (Question 6).  
5. End with roadmap priority (Question 7).

## Action Item Capture Template

Capture each request with explicit tags so follow-up can be prioritized.

- `topic`: short label (for example, metadata split, pagination, errors)
- `request`: one-sentence change request
- `impact`: `high` | `medium` | `low`
- `urgency`: `now` | `next quarter` | `later`
- `owner`: team or person responsible
- `notes`: supporting context or example

### Example Entries

- `topic`: metadata split  
  `request`: clarify `ogm` vs `b1g` source-of-truth rules in API docs and response field docs  
  `impact`: high  
  `urgency`: now  
  `owner`: backend + docs  
  `notes`: ambiguity affects indexing and downstream UI mapping

- `topic`: error payloads  
  `request`: add stable machine-readable error codes and troubleshooting links  
  `impact`: medium  
  `urgency`: next quarter  
  `owner`: backend  
  `notes`: improves client retries and support triage
