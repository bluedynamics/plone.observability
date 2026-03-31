# plone.observability

Kubernetes-style health probes and pluggable metrics for Plone.

## Features

- Liveness, readiness, and startup probes on a separate HTTP port
- Pluggable metrics endpoint (`@@metrics`) with Prometheus and JSON output
- Extensible via ZCA: custom health checks, metric providers, and formatters
