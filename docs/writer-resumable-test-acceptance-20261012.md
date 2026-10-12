# Resumable Drive upload TEST acceptance

The separate owner-authorized Writer OAuth is installed as
`HEALTH_SOURCE_WRITER_RCLONE`. The existing primary read credential was checked
after consent: its actual upload attempt still returned HTTP 403. A different
Google account with reader ACL on the disposable folder also returned HTTP 403.
The actual Drive + restricted SQL integration passed 68 assertions at
`a943f39929aee8665e19ea4518c57a1deb58b7ae`.

`scripts/writer/drive_resumable.py` is a TEST adapter. It requires a freshly
created synthetic folder, or an exact private journal-bound inventory when
reopening that folder. It streams chunks, persists the session before sending
bytes, probes the provider for the accepted offset, and reads completed bytes
through the separate reader account. Session URIs and payloads stay private.
Credential forwarding to other origins and redirects is rejected. Lost
initiation replies stop rather than create another session automatically.
Expired sessions also stop for explicit reconciliation.

An actual 13,631,512-byte synthetic upload was stopped after its first chunk.
The journal was closed/reopened; upload resumed using the provider's offset.
The final success reply was deliberately lost before saving the object ID.
A second journal restart recovered that same completed object with a status
probe. Independent streamed SHA-256 matched all bytes; replay sent no upload
requests and the folder contained one file. The file and folder were trashed.
The Drive-provided session also included `session_crd`: the first strict
validation attempt stopped before uploading bytes. The preserved private
response was used to continue that same session after adding this allowlisted
parameter. The failed evidence was retained.

Ten fault/boundary tests run in CI, including partial recovery, lost final and
initiation replies, changed payload, foreign inventory, duplicate marker,
concurrent workers, object identity rebinding, foreign origin and bad offsets.
Actual TEST evidence is `SOURCE_WRITER_RESUMABLE_ACTUAL_20261012.json` in the
owner's private output folder; no session URI, tokens or payload are published.

This component does not bind a production Source intent, deploy the Writer,
accept production folder ACLs, or authorize cutover. Signed semantic approval
and production integration still require acceptance of their exact version.
