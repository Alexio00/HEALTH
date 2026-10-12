# Source and authorization integration candidate

The disposable PostgreSQL Writer now journals a Source upload before any provider
creation. The Source and its physical location can be inserted only when the
planned full rows, operation, provider marker and current candidate match a fresh
receipt from a separate verifier. Finalization publishes the clinical delta and
Source journal state in the same transaction. Replays keep the same operation.

The verifier invalidates its previous receipt **before** downloading bytes again.
A failed read, changed file, stale receipt or changed candidate blocks publication.
The ordinary Writer cannot attest its own upload or write the journal directly.
The Drive adapter is explicitly synthetic-only, scoped to a newly created empty
test folder. Multipart uploads are bounded to 5 MB; production resumable uploads,
provider immutability and runtime service wiring remain to be implemented.

The authorization bridge accepts an exact intent or candidate digest only from a
separate principal. The TEST Edge broker verifies GitHub OIDC signatures using
issuer JWKS, audience, exact owner actor/repository identifiers, dispatch event,
workflow path, branch and both commit claims. Its server-side RPC is available only
to service_role and a single rendered synthetic schema. No service key reaches
the restricted TCP Writer. The current TEST dispatch proves engineering control;
it is not the final automatic chat authorization transport. Clear owner requests
in chat must eventually map to these exact operation receipts without requiring
a second manual UI approval.

Local TCP suites cover denied self-approval, verifier isolation, receipt expiry,
revocation, replay, concurrent allocation, atomic publication, partial bytes and
lost upload replies. A separate-account actual Drive test uses a read-only token
for byte verification and confirms that token cannot create files. Unit claim
policy checks do not prove JWT signature verification; that needs the signed
network TEST dispatch. Administrator-generated semantic inputs remain simulations.

These overlays are not production migrations. No canonical backend cutover,
existing full-migration finalizer, original-file purge or frozen-baseline release
is authorized by their success. Owner manual PWA acceptance was waived; technical
runtime, backup/restore and exact-operation verification still have to pass.
