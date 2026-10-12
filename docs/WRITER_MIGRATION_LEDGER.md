# Canonical migration ledger reconciliation

The Supabase migration API records the application timestamp. CLI-created
candidate filenames used earlier preparation timestamps. The Writer migration
files now use the observed installed versions:

| Candidate version | Installed canonical version | Migration |
| --- | --- | --- |
| 20261012200609 | 20261012203140 | health_writer_standby_v1 |
| 20261012203258 | 20261012203324 | health_writer_private_rls_and_operator_roles |

Their SQL bytes are unchanged. No migration was reapplied and no installed
history row was changed. Deployment input and stop evidence retain the original
candidate filenames and committed hashes.

Three already-installed historical migrations were also absent from the
repository's canonical directory: planned medication status, the fixed complete
backup reader capability, and its native read-all refinement. Their stored
statements are now mirrored under the exact observed versions. Statement
terminators are restored for the multi-statement planned-status migration; no
new SQL behavior, credentials or medical rows are introduced.

The resulting canonical directory covers all 15 installed versions observed
at reconciliation. This prevents future migration tools from treating already
installed Writer objects as unapplied candidates. Reconstruction from these
files is separate from the accepted complete-archive recovery path, which has
already verified the captured current schema, role catalog and table data.
