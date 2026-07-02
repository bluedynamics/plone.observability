Add `plone.zodb.load_l2_hits` and `plone.zodb.load_pg_queries` span attributes.
When running on zodb-pgjsonb (>= 1.14.3), these split `plone.zodb.objects_loaded`
into shared-cache (L2) hits vs actual PostgreSQL fetches, so the shared-cache hit
ratio (`l2 / (l2 + pg)`) is visible per span — attributing load-time outliers to a
cold/gated cache (all PG) vs high per-load latency (few PG, but slow). Read
best-effort via `getattr`, so it is a no-op on other storages (no new dependency).
