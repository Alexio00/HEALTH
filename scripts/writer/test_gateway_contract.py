"""Синтетические негативные тесты строгого контракта ChatGPT → Writer."""
import unittest
from gateway_contract import GatewayBlocked, capability, safe_status, workflow_envelope

KEY = "writer-" + "a"*32
DIGEST = "b"*64
SHA = "c"*40

def ready():
    return dict(backend_active=True, writer_enabled=True, main_sha=SHA,
                runtime_sha=SHA, workflow_sha=SHA, unfinished_operations=0,
                source_registered=True, restricted_operator_ready=True,
                independent_verifier_ready=True, oauth_owner_verified=True)

class GatewayContractTests(unittest.TestCase):
    def assertBlocked(self, fn, *args):
        with self.assertRaises(GatewayBlocked):
            fn(*args)

    def test_ready_is_explicit(self):
        result = capability(ready())
        self.assertEqual(result.mode, "PRECONDITIONS_MATCH")
        self.assertEqual(result.matching_sha, SHA)
        self.assertNotEqual(result.mode, "WRITE_READY")

    def test_claimed_readiness_never_authorizes_a_write(self):
        # These values could have been supplied by an untrusted JSON caller.
        # Their equality is not evidence of OAuth, owner consent or accepted SHA.
        data = ready()
        for key in ("main_sha", "runtime_sha", "workflow_sha"):
            data[key] = "0" * 40
        observation = capability(data)
        self.assertEqual(observation.mode, "PRECONDITIONS_MATCH")
        self.assertEqual(observation.matching_sha, "0" * 40)
        self.assertNotEqual(observation.mode, "WRITE_READY")
        self.assertFalse(hasattr(observation, "accepted_sha"))

    def test_fail_closed_on_missing_or_forged_readback(self):
        data = ready(); del data["oauth_owner_verified"]
        self.assertBlocked(capability, data)
        data = ready(); data["body_text"] = "SYTHETIC DATA MUST NOT BE HERE"
        self.assertBlocked(capability, data)

    def test_fail_closed_for_any_unverified_identity_or_role(self):
        for field in ("backend_active", "writer_enabled", "source_registered",
                      "restricted_operator_ready", "independent_verifier_ready",
                      "oauth_owner_verified"):
            with self.subTest(field=field):
                data = ready(); data[field] = False
                self.assertEqual(capability(data).mode, "READ_ONLY")

    def test_version_pin_and_concurrency(self):
        for field,value in (("main_sha", "d"*40), ("runtime_sha", "f"*39),
                            ("workflow_sha", None), ("unfinished_operations", 1),
                            ("unfinished_operations", True),
                            ("unfinished_operations", -1)):
            with self.subTest(field=field):
                data = ready(); data[field] = value
                self.assertEqual(capability(data).mode, "READ_ONLY")

    def test_workflow_only_accepts_opaque_identity(self):
        self.assertEqual(set(workflow_envelope(KEY, "intent", DIGEST)),
                         {"request_key", "kind", "digest"})
        self.assertBlocked(workflow_envelope, "REC-20260101-001", "intent", DIGEST)
        self.assertBlocked(workflow_envelope, KEY, "publish", DIGEST)
        self.assertBlocked(workflow_envelope, KEY, "intent", "my medical text")
        self.assertBlocked(workflow_envelope, KEY, "candidate", DIGEST.upper())

    def test_log_status_only_contains_nonmedical_values(self):
        row = {"request_key":KEY,"state":"FINALIZED","result_sha":DIGEST}
        self.assertEqual(safe_status(row), row)
        self.assertBlocked(safe_status, dict(row, source="synthetic-source"))
        self.assertBlocked(safe_status, dict(row, body_text="synthetic note"))
        self.assertBlocked(safe_status, dict(row, state="APPROVED"))

if __name__ == "__main__":
    unittest.main()
