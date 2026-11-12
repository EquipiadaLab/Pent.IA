import asyncio

import pytest

from app.interfaces import LLMClient
from app.llm_bedrock import SAFETY_PREAMBLE, BedrockLLM, LLMError


class FakeClient:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def converse(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("arn:aws:iam::123456789012:role/segredo AKIAABCDEFGHIJKLMNOP")
        return {"output": {"message": {"content": [{"text": " ola "}, {"text": "mundo"}]}}}


def test_implements_contract_and_returns_text():
    fake = FakeClient()
    llm = BedrockLLM(model_id="anthropic.claude-sonnet-5-5", client=fake)
    assert isinstance(llm, LLMClient)
    assert asyncio.run(llm.complete("sys", "prompt")) == "ola mundo"
    assert fake.calls[0]["modelId"] == "anthropic.claude-sonnet-5-5"
    assert SAFETY_PREAMBLE in fake.calls[0]["system"][0]["text"]


def test_secrets_are_scrubbed_before_sending():
    fake = FakeClient()
    asyncio.run(BedrockLLM(client=fake).complete("sys", "chave AKIAABCDEFGHIJKLMNOP e password=hunter2"))
    sent = str(fake.calls[0])
    assert "AKIAABCDEFGHIJKLMNOP" not in sent and "hunter2" not in sent


def test_errors_are_generic_and_do_not_leak():
    with pytest.raises(LLMError) as e:
        asyncio.run(BedrockLLM(client=FakeClient(fail=True)).complete("s", "p"))
    assert "AKIA" not in str(e.value) and "arn:" not in str(e.value)
