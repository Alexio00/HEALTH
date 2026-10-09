# Separate non-mutating Docker test

The diagnostic image and Windows Work handoff are maintained in the private
`Alexio000/SHEDULLER` repository, draft PR
[SHEDULLER #23](https://github.com/Alexio000/SHEDULLER/pull/23).

This test does not authorize a migration, freeze, finalization, cutover, backup or
restore. Active HealthDB remains Drive-native; the test never writes Drive or
Supabase and never opens medical REC/Sources. It creates only synthetic local
fixtures and technical checkouts. No application credentials are sent to GitHub
or supplied to the container. It does not change HEALTH/main or merge existing
SHEDULLER migration PRs #17/#22.

Pinned code:

| Source | Commit | Use |
| --- | --- | --- |
| HEALTH main, merged PR #21 | `803c21c084908a9714264e3382e74134e167e44e` | Original runner offline self-test |
| SHEDULLER main | `54d8e01e10aa38ffe19a4ac2126dc23c3e784b12` | Capture/main launcher offline self-tests |
| SHEDULLER PR #17 | `deb9b3493b3c5f7cfbbaf6d9b87830238b8c6e09` | Synthetic launcher tests, external processes mocked |
| SHEDULLER PR #22 | `1a36db61d9095b82c5d1b4818c7830fe15d92038` | Reviewed context only, excluded from image |
| Diagnostic probe | `191952081ed29de5754165dac232836cf6abec70` | Immutable source for the test archive |

At final readback, SHEDULLER PR #22 had advanced to
`43f9a246e6bfd5bb69b1a366028095a43fae4e71`. Its initially inspected commit above
remains historical context; neither version is included in the test image. No
new-code review or production authorization is inferred from that reference.

[Push CI](https://github.com/Alexio000/SHEDULLER/actions/runs/37907613658)
and [PR CI](https://github.com/Alexio000/SHEDULLER/actions/runs/37907620709)
completed successfully for the probe source HEAD. The workflow builds an
allowlisted context with pinned base/dependencies, uploads/downloads the Docker
archive by immutable artifact ID, checks SHA256, imports it and reruns offline
tests. No production services or application secrets are used in this CI.

The Windows handoff uses a read-only non-root container, no capabilities,
no-new-privileges, 512 MB memory/swap, one CPU, 64 PIDs, an ephemeral tmpfs, and
read-only technical/synthetic bind mounts. Offline checks use network none.
The imported config digest is verified through re-export before selecting the
local immutable runtime ID, supporting both classic Docker and containerd stores.

Transport probes use credential-free HTTPS HEAD and PostgreSQL SSLRequest/TLS
only. No PostgreSQL startup/authentication packet or SQL is sent. HTTPS DNS/TLS
passed with status 401; the direct PostgreSQL hostname did not resolve in the
checking environment, so PostgreSQL TLS remains blocked/unverified. Offline PASS
does not establish production readiness or database privileges.

The published prerelease's `WORK_TASK_RU.md`, `VERIFIED_RELEASE.json`,
`SHA256SUMS`, `CONFIG_DIGEST.txt` and complete tool inventory are the distribution
artifacts. Use their exact release/HEAD/hash pins, never a mutable latest tag.

Published package: [test-probe-20261009-1919520](https://github.com/Alexio000/SHEDULLER/releases/tag/test-probe-20261009-1919520).
Archive SHA256: `1e7ee75348bf66606f1067989e9dd5b3fdb32ab8a59d00c8413bef69cdd90759`.
Config digest: `sha256:efc95affd7c5dd21f56408f3b2e06c84bb421b27a60df661e4beaa8ac2471d58`.
