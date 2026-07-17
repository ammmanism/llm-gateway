# Incident Post-Mortems

## Incident #1: Cache Stampede (2025-12-15)
**Symptom**: Cache miss rate spiked from 15% to 80% during a marketing email blast.
**Root Cause**: The exact cache used a simple TTL expiry. When TTL expired for a popular query, thousands of concurrent requests all recomputed the result.
**Fix**: Implemented **probabilistic early expiration** - refresh the cache early for popular items (e.g., if request count > 100/min, refresh at 80% of TTL).
**Result**: Hit rate returned to 18%, p99 latency dropped 42%.

## Incident #2: Provider API Outage (2025-10-28)
**Symptom**: OpenAI API returned 503 for 4 minutes.
**Action**: Circuit breaker tripped after 3 errors, traffic automatically shifted to Anthropic.
**Recovery**: After 5 seconds, the breaker allowed a test request; once success, it re-opened.
**Lesson**: Monitor circuit-breaker state in dashboard; auto-alert on state changes.

## Incident #3: Tenant Budget Exceeded (2026-01-05)
**Symptom**: Tenant "marketing" exceeded its monthly budget of $500.
**Cause**: Budget was set but not enforced in real-time - only checked at end-of-day.
**Fix**: Switched to **real-time budget checks** in the request pipeline, with a grace period of 10% over budget.
**Result**: No further overshoots; alerts sent to tenant admin when budget reaches 80%.
