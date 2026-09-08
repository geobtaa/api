# Remaining alert decisions — September 8, 2026

The scan after PR #389 contained seven Dependabot alerts and CodeQL #98.
This follow-up patches six dependency alerts and retains two narrowly scoped
exceptions. Dismissals acknowledge the conditions below; they do not disable
scanning or exclude files or dependency families from future analysis.

## Dependency fixes

The frontend overrides require patched versions even where an upstream package
still requests an older version range:

| Dependency | Minimum | Alerts | Reason |
| --- | --- | --- | --- |
| qs | 6.16.0 | #399, #400 | Prevent hostile-object serialization errors and comma-array limit bypasses. |
| body-parser | 1.20.6 | #348 | Reject invalid request-body size limits. |
| @opentelemetry/propagator-jaeger | 2.9.0 | #352 | Handle malformed tracing headers safely, even if Jaeger is enabled later. |
| sharp | 0.35.3 | #354 | Use patched native image-processing libraries in PWA asset generation. |
| esbuild | 0.28.1 | #228 | Fix Windows file-server path traversal, including for contributors who use that server directly. |

The lockfile also refreshes valibot within its existing version range to address
the additional finding from npm audit. Sharp and esbuild overrides cross their
parents' declared minor ranges, so validate both the production build and PWA
asset generation when upgrading these dependencies. Remove overrides only when
the upstream dependency chains reliably resolve patched versions themselves.

## Accepted exceptions

### Dependabot #385: extract-zip

**Decision: tolerable risk for the current development-tool usage.**

The vulnerable extractor is a transitive dependency of pa11y-ci → Puppeteer →
@puppeteer/browsers. It extracts downloaded browser distributions; application
routes do not accept ZIP archives for extraction through this package. GitHub
lists no patched extract-zip release. A malicious or compromised browser archive
could still affect the developer or CI machine, so this is not a claim that the
library is safe or that development dependencies cannot matter.

Revisit when an upstream patch/replacement is available, when browser download
sources change, or before using this extractor with user-supplied archives.

### CodeQL #98: legacy API-key hashing

**Decision: retain compatibility; accept the bounded legacy-hash risk.**

The flagged helper uses SHA-256 for legacy database lookup and process-local
identifiers. Generated API keys are random UUIDv4 values, rather than human-chosen
passwords. New database keys use PBKDF2-HMAC-SHA256 with 600,000 iterations;
legacy stored hashes are upgraded after successful validation. Environment-key
authentication uses a constant-time comparison of the configured key.

Removing the fallback would break older keys that have not yet authenticated
and migrated. Existing stored keys have not been inventoried to prove their
entropy, so this decision is not a blanket assertion that every historical key
is strong. Revisit if human-chosen keys are supported, key generation changes,
or a migration plan makes retiring the fallback feasible. No query suppression
or authentication behavior change is introduced.

## Verification and GitHub state

- Exact frontend installation with lifecycle scripts disabled: passed.
- Frontend tests: 81 files and 999 tests passed.
- Production client/server build: passed.
- PWA asset generation using the repository configuration and a temporary copy
  of the checked-in logo: passed with sharp 0.35.4.
- Focused Node assertions: qs rejects oversized comma arrays and safely
  serializes the hostile constructor/isBuffer object; body-parser rejects an
  invalid limit; Jaeger extraction tolerates malformed percent-encoded headers.
- All installed copies of the five patched packages were checked against the
  six GitHub vulnerable ranges, including comma-separated range bounds. None
  remains affected. Locked versions: qs 6.16.0, body-parser 1.20.8, Jaeger 2.11.0,
  sharp 0.35.4, esbuild 0.28.2.
- npm audit reports one underlying extract-zip advisory across six affected
  dependency-chain entries, all high severity. GitHub dismissal does not remove
  this advisory from npm audit.
- Local frontend cache reset and `git diff --check`: passed.
- No backend implementation changed; the backend suite was not rerun.
- GitHub confirmed #385 dismissed as `tolerable_risk` and CodeQL #98 dismissed
  as `won't fix`, with comments pointing to this rationale. The six patched
  dependency alerts await merging and GitHub's subsequent manifest scan.
