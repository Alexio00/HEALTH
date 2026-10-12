"""Local-provider Source saga component; no Drive, production or clinical writes.

The correlation marker is durable before external creation. Lost replies are
reconciled by marker + object identity + actual readback, never hash alone.
This component does not establish provider ACLs or an independent verifier role.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

class SagaError(RuntimeError):
    pass

class ResponseLost(SagaError):
    pass

def digest(data):
    return hashlib.sha256(data).hexdigest()

class LocalProvider:
    """Disposable immutable object creation adapter; only creates new objects."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(exist_ok=True)

    def create(self, marker, source_id, data, lose_reply=False, partial=False):
        object_id = uuid.uuid4().hex
        folder = self.root / object_id
        folder.mkdir()
        # Metadata first: an interrupted byte write remains discoverable.
        with (folder/'metadata.json').open('x', encoding='utf-8') as f:
            json.dump({'marker':marker,'source_id':source_id,'object_id':object_id},f)
        with (folder/'bytes').open('xb') as f:
            f.write(data[:max(1,len(data)//2)] if partial else data)
        if lose_reply or partial:
            raise ResponseLost('upload_reply_lost')
        return object_id

    def find(self, marker):
        results = []
        for folder in self.root.iterdir():
            if not folder.is_dir() or folder.is_symlink():
                continue
            metadata = folder/'metadata.json'
            if metadata.is_file():
                value = json.loads(metadata.read_text(encoding='utf-8'))
                if value.get('marker') == marker:
                    results.append(value)
        return results

    def readback(self, object_id):
        if not isinstance(object_id,str) or len(object_id)!=32 or any(c not in '0123456789abcdef' for c in object_id):
            raise SagaError('invalid_provider_identity')
        folder = self.root/object_id
        if folder.is_symlink():
            raise SagaError('provider_object_path_escape')
        metadata = json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
        if metadata.get('object_id') != object_id:
            raise SagaError('provider_identity_changed')
        payload = folder/'bytes'
        if payload.is_symlink():
            raise SagaError('provider_payload_path_escape')
        data = payload.read_bytes()
        return metadata, digest(data), len(data)

class Journal:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS upload_intents (
          request_key TEXT PRIMARY KEY, operation_id TEXT NOT NULL,
          candidate_sha TEXT NOT NULL, source_id TEXT NOT NULL UNIQUE,
          marker TEXT NOT NULL UNIQUE, expected_sha TEXT NOT NULL, size_bytes INTEGER NOT NULL,
          state TEXT NOT NULL CHECK(state IN ('PLANNED','UNCERTAIN','VERIFIED','BLOCKED','ABANDONED')),
          object_id TEXT, safe_error TEXT)''')
        self.db.commit()

    def close(self):
        self.db.close()

    def get(self,key):
        row = self.db.execute('SELECT * FROM upload_intents WHERE request_key=?',(key,)).fetchone()
        if row is None:
            raise SagaError('upload_intent_missing')
        return dict(row)

    def plan(self,key,operation_id,candidate_sha,source_id,expected_sha,size_bytes):
        for value in (candidate_sha,expected_sha):
            if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
                raise SagaError('invalid_digest')
        if not isinstance(size_bytes,int) or isinstance(size_bytes,bool) or size_bytes<0:
            raise SagaError('invalid_byte_length')
        try:
            uuid.UUID(operation_id); uuid.UUID(source_id)
        except (ValueError,TypeError,AttributeError):
            raise SagaError('invalid_identity') from None
        binding = (operation_id,candidate_sha,source_id,expected_sha,size_bytes)
        with self.db:
            existing = self.db.execute('SELECT * FROM upload_intents WHERE request_key=?',(key,)).fetchone()
            if existing:
                if tuple(existing[k] for k in ('operation_id','candidate_sha','source_id','expected_sha','size_bytes')) != binding:
                    raise SagaError('idempotency_binding_conflict')
            else:
                self.db.execute('INSERT INTO upload_intents VALUES(?,?,?,?,?,?,?,?,NULL,NULL)',
                                (key,operation_id,candidate_sha,source_id,uuid.uuid4().hex,expected_sha,size_bytes,'PLANNED'))
        return self.get(key)

    def reconcile(self,key,provider):
        row = self.get(key)
        if row['state'] in ('ABANDONED','BLOCKED'):
            raise SagaError('upload_not_recoverable_automatically')
        objects = provider.find(row['marker'])
        if not objects:
            if row['state'] == 'VERIFIED':
                self._block(key,'verified_object_missing')
            return self.get(key)
        if len(objects)!=1:
            self._block(key,'ambiguous_correlation_marker')
        obj = objects[0]
        if obj.get('source_id') != row['source_id']:
            self._block(key,'source_identity_changed')
        if row['object_id'] and obj.get('object_id') != row['object_id']:
            self._block(key,'verified_object_identity_changed')
        try:
            metadata, actual_sha, actual_size = provider.readback(obj['object_id'])
        except (OSError,ValueError,KeyError,SagaError):
            self._block(key,'provider_readback_failed')
        if metadata.get('marker')!=row['marker'] or metadata.get('source_id')!=row['source_id']:
            self._block(key,'readback_identity_mismatch')
        if actual_sha!=row['expected_sha'] or actual_size!=row['size_bytes']:
            self._block(key,'source_digest_or_length_mismatch')
        with self.db:
            self.db.execute("UPDATE upload_intents SET state='VERIFIED',object_id=?,safe_error=NULL WHERE request_key=?",(obj['object_id'],key))
        return self.get(key)

    def upload(self,key,provider,data,lose_reply=False,partial=False):
        row = self.reconcile(key,provider)
        if row['state']=='VERIFIED':
            return row
        if digest(data)!=row['expected_sha'] or len(data)!=row['size_bytes']:
            raise SagaError('candidate_bytes_mismatch_before_upload')
        with self.db:
            self.db.execute("UPDATE upload_intents SET state='UNCERTAIN' WHERE request_key=?",(key,))
        # A crash here leaves the marker and UNKNOWN outcome durable.
        provider.create(row['marker'],row['source_id'],data,lose_reply,partial)
        return self.reconcile(key,provider)

    def receipt(self,key,operation_id,candidate_sha,provider):
        row = self.get(key)
        if row['operation_id']!=operation_id or row['candidate_sha']!=candidate_sha:
            raise SagaError('receipt_operation_candidate_mismatch')
        row = self.reconcile(key,provider)
        if row['state']!='VERIFIED':
            raise SagaError('source_not_verified')
        return {k:row[k] for k in ('operation_id','candidate_sha','source_id','marker','object_id','expected_sha','size_bytes')}

    def abandon(self,key):
        row = self.get(key)
        with self.db:
            self.db.execute("UPDATE upload_intents SET state='ABANDONED' WHERE request_key=?",(key,))
        # Preserve staged/orphan bytes and locator; no physical deletion.
        return self.get(key)

    def _block(self,key,reason):
        with self.db:
            self.db.execute("UPDATE upload_intents SET state='BLOCKED',safe_error=? WHERE request_key=?",(reason,key))
        raise SagaError(reason)
