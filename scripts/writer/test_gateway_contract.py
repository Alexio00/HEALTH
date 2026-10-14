"""Синтетические негативные тесты строгого контракта ChatGPT → Writer."""
import unittest
from types import MappingProxyType
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

    def test_untrusted_json_root_must_be_plain_dict(self):
        for input_value in (None, [], "{}", (), MappingProxyType(ready())):
            with self.subTest(value=type(input_value).__name__):
                self.assertBlocked(capability, input_value)
        status = {"request_key": KEY, "state": "FAILED", "result_sha": DIGEST}
        for input_value in (None, [], MappingProxyType(status)):
            with self.subTest(value=type(input_value).__name__):
                self.assertBlocked(safe_status, input_value)
        self.assertBlocked(capability, {**ready(), "medical_data": "synthetic"})
        self.assertBlocked(safe_status, {"request_key": KEY, "state": "FAILED",
                                       "result_sha": DIGEST, "url": "synthetic"})

    def test_no_boolean_or_string_coercion_in_readiness(self):
        for field in ("backend_active", "writer_enabled", "source_registered",
                      "restricted_operator_ready", "independent_verifier_ready",
                      "oauth_owner_verified"):
            for value in (1, "true", None, [], {}):
                with self.subTest(field=field, value=str(value)):
                    data = ready(); data[field] = value
                    self.assertEqual(capability(data).mode, "READ_ONLY")
        for bad in ("0", 0, False, 0.0, [], {}, None, 2**70):
            with self.subTest(count=str(bad)):
                data = ready(); data["unfinished_operations"] = bad
                self.assertEqual(capability(data).mode, "READ_ONLY")
        for bad in ("C"*40, "c"*39, "c"*41, None, True, [], {}):
            with self.subTest(sha=str(bad)):
                data = ready(); data["main_sha"] = bad
                self.assertEqual(capability(data).mode, "READ_ONLY")

    def test_workflow_rejects_non_str_and_ambiguous_values(self):
        class StrSub(str):
            pass
        self.assertEqual(workflow_envelope(KEY, "candidate", DIGEST)["kind"], "candidate")
        for bad in (None, 1, True, [], {}, StrSub("intent"), "INTENT", "intent ", "publish"):
            with self.subTest(kind=str(bad)):
                self.assertBlocked(workflow_envelope, KEY, bad, DIGEST)
        for bad in (None, [], {}, True, StrSub(KEY), KEY + "0", "writer-" + "A"*32):
            with self.subTest(request_key=str(bad)):
                self.assertBlocked(workflow_envelope, bad, "intent", DIGEST)
        for bad in (None, [], {}, True, StrSub(DIGEST), DIGEST.upper(), DIGEST + "\\n"):
            with self.subTest(digest=str(bad)):
                self.assertBlocked(workflow_envelope, KEY, "intent", bad)

    def test_status_enum_is_strict_and_no_phi_fields(self):
        class StrSub(str):
            pass
        for state in ("PREPARED", "COMMITTED_REGISTRY", "VALIDATED",
                      "FINALIZED", "FAILED", "BLOCKED"):
            row = {"request_key": KEY, "state": state, "result_sha": DIGEST}
            self.assertEqual(safe_status(row), row)
        for bad in (None, True, 1, [], {}, StrSub("FAILED"), "APPROVED", "finalized"):
            with self.subTest(state=str(bad)):
                self.assertBlocked(safe_status, {"request_key": KEY,
                                   "state": bad, "result_sha": DIGEST})
        for field in ("body_text", "owner_text", "source", "token", "original_file"):
            self.assertBlocked(safe_status, {"request_key": KEY,
                               "state": "FAILED", "result_sha": DIGEST,
                               field: "synthetic-nonmedical"})

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
