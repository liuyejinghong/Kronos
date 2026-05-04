"""Schema tests for the local Web API contract."""

from __future__ import annotations

from pydantic import SecretStr

from kronos.web.schemas import LLMSecretUpdateRequest, MaterialImportRequest, MaterialSourceType


def test_llm_secret_request_masks_serialized_value() -> None:
    payload = LLMSecretUpdateRequest(api_key=SecretStr("sk-test-secret"))
    dumped = payload.model_dump(mode="json")

    assert dumped["api_key"] == "**********"
    assert "sk-test-secret" not in str(dumped)


def test_material_import_schema_defaults_to_user_note() -> None:
    payload = MaterialImportRequest(title_zh="一条策略说明", content="策略正文")

    assert payload.source_type == MaterialSourceType.USER_NOTE
    assert payload.tags == []
