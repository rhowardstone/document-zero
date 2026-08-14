"""Adapter tests. No API calls: the SDK client is stubbed, so the contract
between the adapter and the tested orchestration is verified for free."""
import json, types, pytest
import ledger.client as C
from ledger.verify import Verdict

class FakeUsage:
    input_tokens = 100; output_tokens = 20; cache_read_input_tokens = 80

def fake_resp(payload, stop_reason="end_turn", category=None):
    blk = types.SimpleNamespace(type="text", text=json.dumps(payload))
    details = types.SimpleNamespace(category=category) if category else None
    return types.SimpleNamespace(content=[blk], usage=FakeUsage(),
                                 stop_reason=stop_reason, stop_details=details)

class FakeMessages:
    def __init__(self, payload, **kw): self.payload, self.kw, self.seen = payload, kw, []
    def create(self, **kwargs):
        self.seen.append(kwargs)
        return fake_resp(self.payload, **self.kw)

class FakeClient:
    def __init__(self, payload, **kw): self.messages = FakeMessages(payload, **kw)

@pytest.fixture
def cost(): return C.Cost()

def patch(monkeypatch, payload, **kw):
    fc = FakeClient(payload, **kw)
    monkeypatch.setattr(C, "_client", lambda: fc)
    return fc

# --- cost accounting ----------------------------------------------------
def test_cost_is_measured_per_model(cost):
    cost.add("claude-opus-5", FakeUsage()); cost.add("claude-sonnet-5", FakeUsage())
    assert cost.calls == 2 and cost.input_tokens == 200
    assert set(cost.by_model) == {"claude-opus-5", "claude-sonnet-5"}
    assert "2 calls" in cost.summary()

def test_cache_reads_are_tracked_separately(cost):
    cost.add("m", FakeUsage())
    assert cost.cache_read_tokens == 80

# --- extractor ----------------------------------------------------------
def test_extractor_returns_the_json_array_parse_claims_expects(monkeypatch, cost):
    patch(monkeypatch, {"claims": [{"claim_text": "X", "quote": "y", "source_sha": "a",
                                    "confidence": 0.6, "confidence_justification": "j",
                                    "tier": "documented_fact"}]})
    got = json.loads(C.AnthropicExtractor(cost)("prompt"))
    assert isinstance(got, list) and got[0]["claim_text"] == "X"

def test_extractor_constrains_output_with_a_schema(monkeypatch, cost):
    fc = patch(monkeypatch, {"claims": []})
    C.AnthropicExtractor(cost)("prompt")
    fmt = fc.messages.seen[0]["extra_body"]["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert "claims" in fmt["schema"]["properties"]

def test_extractor_caches_the_stable_system_prompt(monkeypatch, cost):
    fc = patch(monkeypatch, {"claims": []})
    C.AnthropicExtractor(cost)("prompt")
    assert fc.messages.seen[0]["system"][0]["cache_control"] == {"type": "ephemeral"}

def test_extractor_records_cost(monkeypatch, cost):
    patch(monkeypatch, {"claims": []})
    C.AnthropicExtractor(cost)("prompt")
    assert cost.calls == 1 and cost.input_tokens == 100

def test_a_refusal_on_extraction_raises_rather_than_returning_empty(monkeypatch, cost):
    patch(monkeypatch, {"claims": []}, stop_reason="refusal", category="cyber")
    with pytest.raises(C.RefusalError, match="declined"):
        C.AnthropicExtractor(cost)("prompt")

# --- verifiers ----------------------------------------------------------
def test_refute_pass_returns_a_verdict(monkeypatch, cost):
    patch(monkeypatch, {"refuted": False, "reason": "quote supports it"})
    v = C.refute_pass(cost).fn({"claim_text": "X"}, [{"sha256": "a"}])
    assert isinstance(v, Verdict) and not v.refuted

def test_a_refusal_on_verification_counts_as_refuted(monkeypatch, cost):
    """A verifier that will not engage has not cleared the claim."""
    patch(monkeypatch, {"refuted": False}, stop_reason="refusal", category="cyber")
    v = C.refute_pass(cost).fn({"claim_text": "X"}, [])
    assert v.refuted and "declined" in v.reason

def test_verifier_is_never_handed_the_extractors_reasoning(monkeypatch, cost):
    fc = patch(monkeypatch, {"refuted": True, "reason": "r"})
    C.refute_pass(cost).fn({"claim_text": "X", "quote": "q"}, [{"sha256": "a", "title": "T"}])
    prompt = fc.messages.seen[0]["messages"][0]["content"]
    assert "claim_text" in prompt and "_reasoning" not in prompt

def test_the_two_passes_use_distinct_models(cost):
    assert C.refute_pass(cost).family != C.lens_pass(cost).family

def test_the_lens_pass_runs_at_lower_effort_than_extraction(monkeypatch, cost):
    fc = patch(monkeypatch, {"refuted": True, "reason": "r"})
    C.lens_pass(cost).fn({"claim_text": "X"}, [])
    assert fc.messages.seen[0]["extra_body"]["output_config"]["effort"] == "low"

def test_verifier_puts_sources_in_the_cached_block_and_the_claim_in_the_turn(monkeypatch, cost):
    """Sources repeat for every claim in a beat; the claim does not. Measured:
    the input tokens are almost entirely the sources."""
    fc = patch(monkeypatch, {"refuted": False, "reason": "r"})
    C.refute_pass(cost).fn({"claim_text": "UNIQUE_CLAIM"},
                           [{"sha256": "a", "title": "Headline here"}])
    call = fc.messages.seen[0]
    sys_block = call["system"][0]
    assert "Headline here" in sys_block["text"], "sources must be cacheable"
    assert sys_block["cache_control"] == {"type": "ephemeral"}
    assert "UNIQUE_CLAIM" in call["messages"][0]["content"]
    assert "Headline here" not in call["messages"][0]["content"], "no duplication"


def test_output_config_rides_in_extra_body_not_as_a_kwarg(monkeypatch, cost):
    """Regression: SDK 0.75.0 rejects output_config as a keyword argument.
    The API accepts it; only the typings lag. extra_body works on both."""
    fc = patch(monkeypatch, {"claims": []})
    C.AnthropicExtractor(cost)("prompt")
    call = fc.messages.seen[0]
    assert "output_config" not in call, "would TypeError on SDK 0.75.0"
    assert "output_config" in call["extra_body"]


class FlakyMessages(FakeMessages):
    """Rejects `effort` once, like a model that doesn't support it."""
    def create(self, **kwargs):
        if "effort" in kwargs["extra_body"]["output_config"]:
            raise Exception("Error code: 400 - This model does not support the effort parameter.")
        return super().create(**kwargs)

def test_a_model_that_rejects_effort_is_retried_without_it(monkeypatch, cost):
    fc = FakeClient({"refuted": False, "reason": "ok"})
    fc.messages = FlakyMessages({"refuted": False, "reason": "ok"})
    monkeypatch.setattr(C, "_client", lambda: fc)
    C._NO_EFFORT.discard("claude-sonnet-5")
    v = C.refute_pass(cost).fn({"claim_text": "X"}, [])
    assert not v.refuted, "effort tunes cost, not correctness — losing it degrades, not fails"
    assert "claude-sonnet-5" in C._NO_EFFORT

def test_the_effort_limitation_is_remembered_not_rediscovered(monkeypatch, cost):
    fc = FakeClient({"refuted": False, "reason": "ok"})
    fc.messages = FlakyMessages({"refuted": False, "reason": "ok"})
    monkeypatch.setattr(C, "_client", lambda: fc)
    C._NO_EFFORT.discard("claude-sonnet-5")
    p = C.refute_pass(cost)
    p.fn({"claim_text": "X"}, []); before = len(fc.messages.seen)
    p.fn({"claim_text": "Y"}, [])
    assert len(fc.messages.seen) == before + 1, "second call must not re-probe"

def test_an_unrelated_400_still_raises(monkeypatch, cost):
    class Broken(FakeMessages):
        def create(self, **kwargs): raise Exception("Error code: 400 - bad schema")
    fc = FakeClient({}); fc.messages = Broken({})
    monkeypatch.setattr(C, "_client", lambda: fc)
    with pytest.raises(Exception, match="bad schema"):
        C.AnthropicExtractor(cost)("prompt")
