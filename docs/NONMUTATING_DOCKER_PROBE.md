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
| Diagnostic probe | `369a68f0d4608ee5d507fa0fb71deaa226bb77e3` | PostgreSQL 17 clients and IPv4 Session pooler probe |

At final readback, SHEDULLER PR #22 had advanced to
`43f9a246e6bfd5bb69b1a366028095a43fae4e71`. Its initially inspected commit above
remains historical context; neither version is included in the test image. No
new-code review or production authorization is inferred from that reference.
At the subsequent pooler readback, PR #22 was MERGED and SHEDULLER/main was
`ed1f0f860aaf6494f61f3128cafe5c971269849c`. This image preserves its older immutable
application pins; it does not validate or substitute that newer main.

[Push CI](https://github.com/Alexio000/SHEDULLER/actions/runs/37911405582)
and [PR CI](https://github.com/Alexio000/SHEDULLER/actions/runs/37911410936)
completed successfully for the probe source HEAD. The workflow builds an
allowlisted context with pinned base/dependencies, uploads/downloads the Docker
archive by immutable artifact ID, checks SHA256, imports it and reruns offline
tests. Clients psql, pg_dump and pg_restore are pinned to PostgreSQL 17.11 from an
official AMD64 image pinned by digest. CI also verifies dump/restore of two
synthetic rows against an ephemeral PostgreSQL 17.11 with network none, no
published ports and no disk volumes. No production services or application
secrets are used in this CI. The diagnostic image contains no PostgreSQL server.

The Windows handoff uses a read-only non-root container, no capabilities,
no-new-privileges, 512 MB memory/swap, one CPU, 64 PIDs, an ephemeral tmpfs, and
read-only technical/synthetic bind mounts. Offline checks use network none.
The imported config digest is verified through re-export before selecting the
local immutable runtime ID, supporting both classic Docker and containerd stores.

Transport probes use credential-free HTTPS HEAD and PostgreSQL SSLRequest/TLS
only. No PostgreSQL startup/authentication packet or SQL is sent. HTTPS DNS/TLS
passed with status 401. The owner supplied the Session pooler endpoint from the
Dashboard: `aws-0-us-west-1.pooler.supabase.com:5432`. Both IPv4 addresses passed
TCP and TLS 1.3 with verified hostname and the owner-supplied public Supabase CA.
The downloaded updated image passed the full Windows runner with that CA,
read-only mounts, limits and all negative cases. The CA remains local and is not
bundled or published. Direct IPv6 connectivity remains blocked; Session pooler
transport PASS does not establish authenticated access, database privileges,
direct connectivity or production readiness. Real HEALTH dumps were not made.

The published prerelease's `WORK_TASK_RU.md`, `VERIFIED_RELEASE.json`,
`SHA256SUMS`, `CONFIG_DIGEST.txt` and complete tool inventory are the distribution
artifacts. Use their exact release/HEAD/hash pins, never a mutable latest tag.

Published package: [test-probe-pg17-session-20261009-369a68f](https://github.com/Alexio000/SHEDULLER/releases/tag/test-probe-pg17-session-20261009-369a68f).
Archive SHA256: `d0792045f4d2c3b08e8ef7f4dfa33172efba37aea34770863e31544e17fa5144`.
Config digest: `sha256:9d57c8a6d1893659039ffe78f0263a765c2ae8e63b2f85fd8a5abe357df28801`.
The previous diagnostic package remains available as a historical release.
