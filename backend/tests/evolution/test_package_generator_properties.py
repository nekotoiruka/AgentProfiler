"""PackageGenerator プロパティベーステスト

Feature: agent-evolution
Property 17: Package structure completeness
Property 18: System prompt file round-trip
Property 19: Technology tool generation
Property 20: Workflow tool schema generation
Property 21: Zip archive round-trip
Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 15.2
"""

import io
import json
import zipfile

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models.scores import NormalizedScores
from app.models.profile import (
  BaseOS, ContextLayers, ProfileOutput, Persona, CommunicationTone,
)
from app.evolution.prompt_engine import PromptEngine
from app.evolution.package_generator import (
  PackageGenerator, TECH_IDENTIFIERS, SKILL_KEYWORDS,
)


# --- Hypothesis ストラテジー ---

_valid_profile_id_st = st.integers(min_value=0, max_value=999999).map(
  lambda n: f"prof_{n:06d}"
)

_valid_axis_score_st = st.floats(
  min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)

_valid_axes_st = st.builds(
  NormalizedScores,
  extroverted_introverted=_valid_axis_score_st,
  sensing_intuition=_valid_axis_score_st,
  thinking_feeling=_valid_axis_score_st,
  judging_perceiving=_valid_axis_score_st,
)

_valid_decision_style_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N")),
  min_size=1,
  max_size=30,
)

_valid_do_not_list_st = st.lists(
  st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=30,
  ),
  min_size=1,
  max_size=4,
)

_valid_base_os_st = st.builds(
  BaseOS,
  axes=_valid_axes_st,
  decision_style=_valid_decision_style_st,
  do_not_list=_valid_do_not_list_st,
)

# lexical_tags: 5〜10件。docker/mcp の有無をテストするために
# 既知のテック識別子をサブセットとして混入可能にする
_tech_tag_st = st.sampled_from(list(TECH_IDENTIFIERS.keys()))
_random_tag_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N")),
  min_size=1,
  max_size=20,
)

# docker を含む lexical_tags
_lexical_tags_with_docker_st = st.lists(
  _random_tag_st, min_size=4, max_size=9
).map(lambda tags: tags + ["docker"])

# docker を含まない lexical_tags (テック識別子からdocker除外)
_non_docker_tech_tags_st = st.sampled_from(
  [k for k in TECH_IDENTIFIERS.keys() if k != "docker"]
)
_lexical_tags_without_docker_st = st.lists(
  _random_tag_st, min_size=5, max_size=10
).filter(lambda tags: "docker" not in [t.lower() for t in tags])

# 汎用 lexical_tags: ランダムタグ + テック識別子のサブセット
_lexical_tags_st = st.lists(
  st.one_of(_tech_tag_st, _random_tag_st),
  min_size=5,
  max_size=10,
)

# semantic_contexts: スキルキーワードを含む/含まないバリエーション
_skill_keyword_st = st.sampled_from(list(SKILL_KEYWORDS.keys()))
_context_value_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
  min_size=10,
  max_size=100,
)
_semantic_contexts_st = st.dictionaries(
  keys=st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
  ),
  values=_context_value_st,
  min_size=1,
  max_size=3,
)

_valid_context_layers_st = st.just(
  ContextLayers(base_os=1, lexical_tags=2, semantic_contexts=3)
)

# 汎用 ProfileOutput
_valid_profile_st = st.builds(
  ProfileOutput,
  profile_id=_valid_profile_id_st,
  base_os=_valid_base_os_st,
  lexical_tags=_lexical_tags_st,
  semantic_contexts=_semantic_contexts_st,
  context_layers=_valid_context_layers_st,
)

# docker を含む ProfileOutput
_profile_with_docker_st = st.builds(
  ProfileOutput,
  profile_id=_valid_profile_id_st,
  base_os=_valid_base_os_st,
  lexical_tags=_lexical_tags_with_docker_st,
  semantic_contexts=_semantic_contexts_st,
  context_layers=_valid_context_layers_st,
)

# docker を含まない ProfileOutput
_profile_without_docker_st = st.builds(
  ProfileOutput,
  profile_id=_valid_profile_id_st,
  base_os=_valid_base_os_st,
  lexical_tags=_lexical_tags_without_docker_st,
  semantic_contexts=_semantic_contexts_st,
  context_layers=_valid_context_layers_st,
)

# agent_id と display_name
_agent_id_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N")),
  min_size=1,
  max_size=20,
)
_display_name_st = st.text(
  alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
  min_size=1,
  max_size=30,
)


# =============================================================================
# Property 17: Package structure completeness
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_valid_profile_st,
  agent_id=_agent_id_st,
  display_name=_display_name_st,
)
def test_generate_always_contains_required_files(
  profile: ProfileOutput, agent_id: str, display_name: str
) -> None:
  """generate() は常に README.md, config.json, system_prompt.md,
  tools/project_context.json を含む。

  **Validates: Requirements 14.1, 14.5**
  """
  engine = PromptEngine(max_tokens=8000)
  generator = PackageGenerator(engine)
  files = generator.generate(profile, agent_id, display_name)

  required_paths = {
    "README.md",
    "config.json",
    "system_prompt.md",
    "tools/project_context.json",
  }
  for path in required_paths:
    assert path in files, (
      f"Required file '{path}' not found in generated files. "
      f"Got: {sorted(files.keys())}"
    )


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_valid_profile_st,
  agent_id=_agent_id_st,
  display_name=_display_name_st,
)
def test_config_json_contains_required_fields(
  profile: ProfileOutput, agent_id: str, display_name: str
) -> None:
  """config.json は agent_id, profile_id, display_name, version, base_os を含む。

  **Validates: Requirements 14.1, 14.5**
  """
  engine = PromptEngine(max_tokens=8000)
  generator = PackageGenerator(engine)
  files = generator.generate(profile, agent_id, display_name)

  config = json.loads(files["config.json"])
  assert config["agent_id"] == agent_id
  assert config["profile_id"] == profile.profile_id
  assert config["display_name"] == display_name
  assert "version" in config
  assert "base_os" in config


# =============================================================================
# Property 18: System prompt file round-trip
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_valid_profile_st,
  agent_id=_agent_id_st,
  display_name=_display_name_st,
)
def test_system_prompt_contains_prompt_engine_output(
  profile: ProfileOutput, agent_id: str, display_name: str
) -> None:
  """system_prompt.md は PromptEngine.generate() の出力を含む。

  **Validates: Requirements 14.2**
  """
  engine = PromptEngine(max_tokens=8000)
  generator = PackageGenerator(engine)
  files = generator.generate(profile, agent_id, display_name)

  # PromptEngine の出力を取得
  prompt_result = engine.generate(profile)

  # system_prompt.md は PromptEngine 出力で始まる
  assert files["system_prompt.md"].startswith(prompt_result.prompt), (
    "system_prompt.md does not start with PromptEngine output"
  )


# =============================================================================
# Property 19: Technology tool generation
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_profile_with_docker_st,
  agent_id=_agent_id_st,
  display_name=_display_name_st,
)
def test_docker_tag_generates_docker_workflow_tool(
  profile: ProfileOutput, agent_id: str, display_name: str
) -> None:
  """lexical_tags に "docker" が含まれる場合、
  tools/docker_workflow.json が生成され、有効な JSON である。

  **Validates: Requirements 14.3**
  """
  engine = PromptEngine(max_tokens=8000)
  generator = PackageGenerator(engine)
  files = generator.generate(profile, agent_id, display_name)

  assert "tools/docker_workflow.json" in files, (
    f"docker_workflow.json not found when 'docker' in lexical_tags. "
    f"lexical_tags={profile.lexical_tags}"
  )
  # 有効な JSON であることを検証
  content = json.loads(files["tools/docker_workflow.json"])
  assert isinstance(content, dict)
  assert "name" in content


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_profile_without_docker_st,
  agent_id=_agent_id_st,
  display_name=_display_name_st,
)
def test_no_docker_tag_no_docker_workflow_tool(
  profile: ProfileOutput, agent_id: str, display_name: str
) -> None:
  """lexical_tags に "docker" が含まれない場合、
  tools/docker_workflow.json は生成されない。

  **Validates: Requirements 14.3**
  """
  engine = PromptEngine(max_tokens=8000)
  generator = PackageGenerator(engine)
  files = generator.generate(profile, agent_id, display_name)

  assert "tools/docker_workflow.json" not in files, (
    f"docker_workflow.json found but 'docker' not in lexical_tags. "
    f"lexical_tags={profile.lexical_tags}"
  )


# =============================================================================
# Property 20: Workflow tool schema generation
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_valid_profile_st,
  agent_id=_agent_id_st,
  display_name=_display_name_st,
)
def test_generated_tool_files_are_valid_json(
  profile: ProfileOutput, agent_id: str, display_name: str
) -> None:
  """tools/ ディレクトリ内の全 .json ファイルは有効な JSON である。

  **Validates: Requirements 14.4**
  """
  engine = PromptEngine(max_tokens=8000)
  generator = PackageGenerator(engine)
  files = generator.generate(profile, agent_id, display_name)

  for path, content in files.items():
    if path.startswith("tools/") and path.endswith(".json"):
      try:
        parsed = json.loads(content)
        assert isinstance(parsed, dict), (
          f"Tool file '{path}' is not a JSON object"
        )
      except json.JSONDecodeError as e:
        raise AssertionError(
          f"Tool file '{path}' is not valid JSON: {e}"
        ) from e


# =============================================================================
# Property 21: Zip archive round-trip
# Feature: agent-evolution
# =============================================================================


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_valid_profile_st,
  agent_id=_agent_id_st,
  display_name=_display_name_st,
)
def test_build_zip_produces_valid_zip(
  profile: ProfileOutput, agent_id: str, display_name: str
) -> None:
  """build_zip() は有効な ZIP バイト列を生成する。

  **Validates: Requirements 15.2**
  """
  engine = PromptEngine(max_tokens=8000)
  generator = PackageGenerator(engine)
  zip_bytes = generator.build_zip(profile, agent_id, display_name)

  assert isinstance(zip_bytes, bytes)
  assert len(zip_bytes) > 0

  # 有効な ZIP として読み取れることを確認
  buffer = io.BytesIO(zip_bytes)
  assert zipfile.is_zipfile(buffer)


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
  profile=_valid_profile_st,
  agent_id=_agent_id_st,
  display_name=_display_name_st,
)
def test_build_zip_contains_same_files_as_generate(
  profile: ProfileOutput, agent_id: str, display_name: str
) -> None:
  """build_zip() の ZIP を展開すると、generate() と同一のファイルセットを含む。

  **Validates: Requirements 15.2**
  """
  engine = PromptEngine(max_tokens=8000)
  generator = PackageGenerator(engine)

  # generate() の結果を取得
  files = generator.generate(profile, agent_id, display_name)

  # build_zip() の結果を展開
  zip_bytes = generator.build_zip(profile, agent_id, display_name)
  buffer = io.BytesIO(zip_bytes)
  with zipfile.ZipFile(buffer, "r") as zf:
    zip_names = set(zf.namelist())

    # ファイルパスが完全一致
    assert zip_names == set(files.keys()), (
      f"ZIP file set mismatch.\n"
      f"Expected: {sorted(files.keys())}\n"
      f"Got: {sorted(zip_names)}"
    )

    # 各ファイルの内容が一致
    for path, expected_content in files.items():
      actual_content = zf.read(path).decode("utf-8")
      assert actual_content == expected_content, (
        f"Content mismatch for '{path}'"
      )
