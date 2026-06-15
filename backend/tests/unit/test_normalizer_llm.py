"""LLMNormalizer ユニットテスト"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.decision_engine.normalizer_llm import LLMNormalizer, NormalizationResult


@pytest.fixture
def mock_llm_client():
  """LLMClient のモック（enabled=True）"""
  client = MagicMock()
  client.enabled = True
  client._client = MagicMock()
  return client


@pytest.fixture
def disabled_llm_client():
  """LLMClient のモック（enabled=False）"""
  client = MagicMock()
  client.enabled = False
  return client


@pytest.fixture
def normalizer(mock_llm_client):
  """テスト用 LLMNormalizer インスタンス"""
  return LLMNormalizer(llm_client=mock_llm_client, model="gpt-4.1-mini")


class TestNormalize:
  """normalize() メソッドのテスト"""

  @pytest.mark.asyncio
  async def test_returns_none_when_client_disabled(self, disabled_llm_client):
    """LLM クライアントが無効の場合は None を返す"""
    normalizer = LLMNormalizer(llm_client=disabled_llm_client)
    result = await normalizer.normalize("質問", "回答")
    assert result is None

  @pytest.mark.asyncio
  async def test_successful_normalization(self, normalizer, mock_llm_client):
    """正常系: LLM レスポンスから NormalizationResult を生成"""
    valid_response = json.dumps({
      "tags": [{"type": "value_tag", "value": "品質重視"}],
      "policy_text": "when_deadline: 品質を優先する",
    })
    mock_response = MagicMock()
    mock_response.output_text = valid_response
    mock_llm_client._client.responses.create.return_value = mock_response

    result = await normalizer.normalize("あなたの優先事項は？", "品質を大切にしています")

    assert result is not None
    assert isinstance(result, NormalizationResult)
    assert len(result.tags) == 1
    assert result.tags[0]["type"] == "value_tag"
    assert result.tags[0]["value"] == "品質重視"
    assert result.policy_text == "when_deadline: 品質を優先する"

  @pytest.mark.asyncio
  @patch("app.decision_engine.normalizer_llm.time.sleep")
  async def test_retries_on_exception(self, mock_sleep, normalizer, mock_llm_client):
    """LLM 呼び出し失敗時にリトライする"""
    valid_response = json.dumps({
      "tags": [{"type": "behavior_tag", "value": "即断即決"}],
      "policy_text": "when_decision_needed: すぐに判断する",
    })
    mock_response = MagicMock()
    mock_response.output_text = valid_response

    # 1回目失敗、2回目成功
    mock_llm_client._client.responses.create.side_effect = [
      Exception("API error"),
      mock_response,
    ]

    result = await normalizer.normalize("質問", "回答")

    assert result is not None
    assert result.tags[0]["type"] == "behavior_tag"
    mock_sleep.assert_called_once_with(1)  # 2^0 = 1

  @pytest.mark.asyncio
  @patch("app.decision_engine.normalizer_llm.time.sleep")
  async def test_returns_none_after_max_retries(self, mock_sleep, normalizer, mock_llm_client):
    """最大リトライ回数超過後は None を返す"""
    mock_llm_client._client.responses.create.side_effect = Exception("API error")

    result = await normalizer.normalize("質問", "回答")

    assert result is None
    # 3回呼び出し（初回 + 2リトライ）
    assert mock_llm_client._client.responses.create.call_count == 3
    # sleep は2回（リトライ間のみ）
    assert mock_sleep.call_count == 2

  @pytest.mark.asyncio
  @patch("app.decision_engine.normalizer_llm.time.sleep")
  async def test_retries_on_parse_failure(self, mock_sleep, normalizer, mock_llm_client):
    """パース失敗時にもリトライする"""
    invalid_response = MagicMock()
    invalid_response.output_text = "not valid json"

    valid_response = MagicMock()
    valid_response.output_text = json.dumps({
      "tags": [{"type": "prohibition_tag", "value": "感情的判断を避ける"}],
      "policy_text": "when_conflict: 論理的に対処する",
    })

    mock_llm_client._client.responses.create.side_effect = [
      invalid_response,
      valid_response,
    ]

    result = await normalizer.normalize("質問", "回答")

    assert result is not None
    assert result.tags[0]["type"] == "prohibition_tag"


class TestBuildPrompt:
  """_build_prompt() メソッドのテスト"""

  def test_includes_question_and_answer(self, normalizer):
    """プロンプトに質問と回答が含まれる"""
    prompt = normalizer._build_prompt("テスト質問", "テスト回答")
    assert "テスト質問" in prompt
    assert "テスト回答" in prompt


class TestCallLLM:
  """_call_llm() メソッドのテスト"""

  def test_uses_structured_output(self, normalizer, mock_llm_client):
    """Structured Output JSON Schema を使用する"""
    mock_response = MagicMock()
    mock_response.output_text = "{}"
    mock_llm_client._client.responses.create.return_value = mock_response

    normalizer._call_llm("test prompt")

    call_kwargs = mock_llm_client._client.responses.create.call_args[1]
    assert call_kwargs["model"] == "gpt-4.1-mini"
    assert call_kwargs["text"]["format"]["type"] == "json_schema"
    assert call_kwargs["text"]["format"]["name"] == "normalization_result"
    assert call_kwargs["text"]["format"]["strict"] is True

  def test_uses_configured_model(self, mock_llm_client):
    """コンストラクタで指定したモデルを使用する"""
    normalizer = LLMNormalizer(llm_client=mock_llm_client, model="gpt-4o")
    mock_response = MagicMock()
    mock_response.output_text = "{}"
    mock_llm_client._client.responses.create.return_value = mock_response

    normalizer._call_llm("test")

    call_kwargs = mock_llm_client._client.responses.create.call_args[1]
    assert call_kwargs["model"] == "gpt-4o"


class TestParseResponse:
  """_parse_response() メソッドのテスト"""

  def test_valid_response(self, normalizer):
    """正常な JSON レスポンスをパースする"""
    response = json.dumps({
      "tags": [
        {"type": "value_tag", "value": "効率重視"},
        {"type": "behavior_tag", "value": "事前計画を立てる"},
      ],
      "policy_text": "when_project_start: まず計画を策定する",
    })
    result = normalizer._parse_response(response)

    assert result is not None
    assert len(result.tags) == 2
    assert result.tags[0] == {"type": "value_tag", "value": "効率重視"}
    assert result.tags[1] == {"type": "behavior_tag", "value": "事前計画を立てる"}
    assert result.policy_text == "when_project_start: まず計画を策定する"

  def test_invalid_json(self, normalizer):
    """無効な JSON は None を返す"""
    result = normalizer._parse_response("not json")
    assert result is None

  def test_empty_tags(self, normalizer):
    """空の tags リストは None を返す"""
    response = json.dumps({"tags": [], "policy_text": "when_x: y"})
    result = normalizer._parse_response(response)
    assert result is None

  def test_invalid_tag_type(self, normalizer):
    """無効なタグタイプは None を返す"""
    response = json.dumps({
      "tags": [{"type": "invalid_tag", "value": "test"}],
      "policy_text": "when_x: y",
    })
    result = normalizer._parse_response(response)
    assert result is None

  def test_tag_value_too_long(self, normalizer):
    """50文字超のタグ値は None を返す"""
    response = json.dumps({
      "tags": [{"type": "value_tag", "value": "a" * 51}],
      "policy_text": "when_x: y",
    })
    result = normalizer._parse_response(response)
    assert result is None

  def test_tag_value_exactly_50_chars(self, normalizer):
    """50文字ちょうどのタグ値は受け入れる"""
    response = json.dumps({
      "tags": [{"type": "value_tag", "value": "a" * 50}],
      "policy_text": "when_x: y",
    })
    result = normalizer._parse_response(response)
    assert result is not None

  def test_empty_tag_value(self, normalizer):
    """空のタグ値は None を返す"""
    response = json.dumps({
      "tags": [{"type": "value_tag", "value": ""}],
      "policy_text": "when_x: y",
    })
    result = normalizer._parse_response(response)
    assert result is None

  def test_empty_policy_text(self, normalizer):
    """空の policy_text は None を返す"""
    response = json.dumps({
      "tags": [{"type": "value_tag", "value": "test"}],
      "policy_text": "",
    })
    result = normalizer._parse_response(response)
    assert result is None

  def test_policy_text_not_starting_with_when(self, normalizer):
    """'when_' で始まらない policy_text は None を返す"""
    response = json.dumps({
      "tags": [{"type": "value_tag", "value": "test"}],
      "policy_text": "always do this",
    })
    result = normalizer._parse_response(response)
    assert result is None

  def test_all_valid_tag_types(self, normalizer):
    """全4種のタグタイプが受け入れられる"""
    response = json.dumps({
      "tags": [
        {"type": "value_tag", "value": "a"},
        {"type": "behavior_tag", "value": "b"},
        {"type": "prohibition_tag", "value": "c"},
        {"type": "condition_tag", "value": "d"},
      ],
      "policy_text": "when_test: テスト",
    })
    result = normalizer._parse_response(response)
    assert result is not None
    assert len(result.tags) == 4

  def test_missing_tags_key(self, normalizer):
    """tags キーがない場合は None を返す"""
    response = json.dumps({"policy_text": "when_x: y"})
    result = normalizer._parse_response(response)
    assert result is None

  def test_missing_policy_text_key(self, normalizer):
    """policy_text キーがない場合は None を返す"""
    response = json.dumps({"tags": [{"type": "value_tag", "value": "a"}]})
    result = normalizer._parse_response(response)
    assert result is None
