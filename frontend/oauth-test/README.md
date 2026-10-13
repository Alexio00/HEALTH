# HEALTH-TEST consent UI: release and threat review

This page supports only the isolated OAuth/synthetic-queue acceptance probe.
It cannot prepare, confirm or finalize a clinical Writer operation.

Runtime values are not committed: a fixed trusted TEST HTTPS endpoint returns
only a modern publishable API key, registered public client ID and exact
ChatGPT callback. These three values are intentionally public browser parameters,
not server credentials. Their source row remains in private TEST configuration.
The page rejects extra fields, legacy JWT keys, malformed client IDs and other
callback origins/paths. It never accepts an Auth/API root from that response.

The separate server route uses an explicit three-field projection. It cannot
return owner UUID, service credentials, policy or queue data. Missing server
credentials/configuration fails closed. Its availability does not enable MCP
authorization; the independently disabled private policy still gates tool calls.
CORS permits the existing Pages origin; CORS is not authentication.

The login form stays disabled without a valid authorization ID and validated
configuration. The password goes only to fixed HEALTH-TEST Auth over HTTPS,
is cleared after the response or error, and is never logged or stored. Access
tokens stay in page memory. Auth details are read again before consent;
exact client/callback and only openid must still match. An unrecognized response
or already-granted redirect-only response fails closed rather than auto-approving.
Consent for this test does not constitute approval of any clinical write.

The existing CSP allows only local scripts/styles and fixed TEST network origin;
no third-party scripts are added. OAuth pages/query URLs are excluded from the
PWA worker's offline cache. This PR does not edit the worker or release workflows.
The Pages origin and its reviewed static source remain trusted login UI; changes
to them must retain protected PR/CI/release review. No password/token is a fixture.

Tests exercise malformed/extra configuration, callback/scope rejection, network
failure, invalid authorization IDs and the disabled login gate. They do not prove
real password login, owner OAuth, S256-only enforcement or clinical correctness.
Real OAuth/negative-flow evidence and an independent production security audit
remain required. A public Pages release does not change HEALTH/main acceptance.
