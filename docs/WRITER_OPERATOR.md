# Bounded Writer operation

The canonical Writer is installed through versioned migrations into the private
`health_writer` schema. Installation starts disabled. Preparing an operation,
projecting a candidate, uploading a Source and publishing require the enabled
runtime, a finalized accepted migration, the registered primary Source folder
and the exact accepted code pin. Installing the schema does not release the
frozen original project or perform owner cutover.

`chat_worker.py` performs only bounded RPC operations. Medical intent, candidate
rows, review projections and evidence remain in private local files. The ordinary
`health_writer` login inherits only `health_writer_executor`. The separate
`health_writer_verifier_login` inherits only `health_writer_verifier`; neither
login can select or modify clinical tables directly, edit private control tables,
become the owner, or self-authorize. Provision connection files and CA pins
privately. Use separate operator profiles: the writing profile contains no
verifier connection or independent Google credential, and neither profile
contains a database owner credential.

Each clear owner chat request becomes an immutable intent with the exact message
digest and conversation reference. The operator dispatches
`writer-authorization.yml` automatically using the configured GitHub owner.
GitHub receives only an opaque request key, approval kind and digest. The Edge
broker verifies the GitHub signature, issuer, audience, age, owner and repository
IDs, exact main workflow and accepted commit before invoking a fixed server-only
RPC. It never receives medical payloads or lets the request select a schema.
Writer has no authorization broker service key. Repository changes require an
accepted new commit before further authorizations can run.

The writer prepares a durable operation and proposes an exact before/after
candidate. The independent verifier reads only that approved candidate through
`review_candidate`, checks the registered semantic rules, provides actual
rule-specific methodology and evidence digests, and verifies changed lab rows
against literal originals. The client does not generate PASS receipts. An AI
performing this review must retain the exact evidence locally and use the
separate verifier profile. Missing, expired or differently bound evidence
blocks publication. Finalization publishes the delta, validation results and
audit together; repeating finalization returns the same operation.

Source uploads use an owner-only adapter with the durable SQL resumable journal.
It cannot attest independent verification. The separate reader performs a full
byte digest and verifies identity, owner, parent, marker, protocol and stable
provider metadata before issuing an exact candidate-bound receipt. An uncertain
upload resumes or reconciles the same provider object; existing originals are
not overwritten. Backup capture and Writer use the same exclusion boundary.

An owner-approved historical Record exception permits only the date/ID equality
check for one exact whole row. The private baseline and owner-decision digests
bind that exception; any field change invalidates it. The current operation's
rule 11 audit explicitly discloses its use. Other fields and new records remain
strict. No public migration contains a private Record ID or clinical value.

Synthetic suites exercise local restricted TCP, actual Google upload recovery
and independent byte readback. Isolated Supabase TEST runs exercise the canonical
RPC engine with real signed GitHub OIDC and idempotent publication. Administrator
semantic receipts in those synthetic runs are simulations; their PASS is not
evidence for a production medical operation. Each such operation still needs
its own current independent review.

Recovery first verifies the exact captured database, roles and fingerprints.
Then the recovery executor deliberately disables Writer, clears its code pin
and disables upload folders. Pending operations, NNN reservations, approvals,
audit rows and resumable session URIs remain preserved. After independent
verification of a recreated Source root, recovery binds that new root while
Writer stays disabled. Activation and reconciliation require separate current
acceptance; restoring an archive never resumes pending writes automatically.
