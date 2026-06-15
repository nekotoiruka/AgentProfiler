"""Agent Pack パッケージ自動生成

ProfileOutput + agent_id から Agent Skills 仕様準拠のパッケージを生成する。
出力構造:
  agent_pack_{agent_id}.zip
  ├── README.md
  ├── config.json
  ├── system_prompt.md
  ├── skills/
  │   ├── reflection-wall/SKILL.md
  │   ├── code-review-rules/SKILL.md
  │   └── focus-timer/SKILL.md
  └── tools/
      └── project_context.json

📖 参照: docs/agent_skills_specification.md
"""

import io
import json
import logging
import zipfile

from app.evolution.prompt_engine import PromptEngine
from app.models.profile import ProfileOutput

logger = logging.getLogger(__name__)

# semantic_contexts のドメイン/値からスキル生成を判定するキーワード
SKILL_KEYWORDS: dict[str, str] = {
  "モーニングページ": "reflection_wall",
  "内省": "reflection_wall",
  "壁打ち": "reflection_wall",
  "bullet journal": "reflection_wall",
  "バレットジャーナル": "reflection_wall",
  "コードレビュー": "code_review_rules",
  "美学": "code_review_rules",
  "設計原則": "code_review_rules",
  "pomodoro": "focus_timer",
  "ポモドーロ": "focus_timer",
  "time blocking": "focus_timer",
}

# lexical_tags から技術スタックを識別するためのマッピング
TECH_IDENTIFIERS: dict[str, str] = {
  "python": "python",
  "fastapi": "fastapi",
  "vue": "vue",
  "typescript": "typescript",
  "react": "react",
  "nodejs": "nodejs",
  "docker": "docker",
  "azure-openai": "azure-openai",
  "mcp": "mcp",
}

# スキル別の SKILL.md テンプレート
_SKILL_TEMPLATES: dict[str, dict[str, str]] = {
  "reflection_wall": {
    "name": "reflection-wall",
    "description": (
      "Supports morning pages, journaling, and introspective "
      "brainstorming sessions. Use when the user wants to think "
      "through problems, reflect on decisions, or generate new ideas "
      "through structured dialogue."
    ),
    "body": """\
# Reflection Wall Skill

## When to use
- User asks to brainstorm or think through a problem
- User wants to do morning pages or journaling
- User seeks introspective dialogue or a sounding board

## Approach
1. Ask open-ended questions to help the user articulate their thoughts
2. Reflect back key themes and patterns you notice
3. Avoid giving direct advice unless explicitly asked
4. Encourage deeper exploration of ideas

## Guardrails
- Never dismiss or minimize the user's feelings or ideas
- Keep the focus on the user's perspective, not your own
""",
  },
  "code_review_rules": {
    "name": "code-review-rules",
    "description": (
      "Applies the user's aesthetic and design principles when "
      "reviewing code. Use when asked to review PRs, check code "
      "quality, or suggest improvements based on established standards."
    ),
    "body": """\
# Code Review Rules Skill

## When to use
- User asks to review code or a PR
- User wants code quality assessment
- User asks for refactoring suggestions

## Review Principles
1. Check alignment with the user's stated design principles
2. Evaluate readability and maintainability
3. Identify potential performance issues
4. Verify error handling completeness
5. Assess test coverage adequacy

## Standards
- Follow DRY (Don't Repeat Yourself) principle
- Prefer explicit over implicit patterns
- Keep functions focused and small
""",
  },
  "focus_timer": {
    "name": "focus-timer",
    "description": (
      "Manages Pomodoro and time blocking sessions for focused work. "
      "Use when the user wants to structure their work time, set focus "
      "intervals, or track productivity sessions."
    ),
    "body": """\
# Focus Timer Skill

## When to use
- User wants to start a Pomodoro session
- User asks for time blocking assistance
- User needs help structuring focused work time

## Approach
1. Help define the task scope for the session
2. Set appropriate focus interval (default: 25 min work / 5 min break)
3. Provide session summaries at the end of each interval
4. Track completed sessions and suggest breaks

## Guardrails
- Do not interrupt during focus periods unless critical
- Respect the user's chosen interval lengths
""",
  },
}


class PackageGenerator:
  """ProfileOutput + agent_id → Agent Pack Zip 生成

  出力構造:
  - README.md: セットアップガイド
  - config.json: メタデータ + 4軸スコア + decision_style + do_not_list
  - system_prompt.md: PromptEngine 出力 (Markdown 形式)
  - skills/: Agent Skills 標準準拠スキル定義
  - tools/project_context.json: 技術スタックの静的コンテキスト
  """

  def __init__(self, prompt_engine: PromptEngine):
    self._prompt_engine = prompt_engine

  def generate(
    self, profile: ProfileOutput, agent_id: str, display_name: str
  ) -> dict[str, str]:
    """パッケージ全ファイルを生成し、パス → コンテンツの辞書で返す。

    Returns:
      {"README.md": "...", "config.json": "...", "system_prompt.md": "...", ...}
    """
    files: dict[str, str] = {}
    files["README.md"] = self._generate_readme(profile, agent_id, display_name)
    files["config.json"] = self._generate_config_json(
      profile, agent_id, display_name
    )
    files["system_prompt.md"] = self._generate_system_prompt_md(profile)

    # skills/ 生成
    skills = self._generate_skills(profile)
    for path, content in skills:
      files[path] = content

    # Decision Engine: skills/decision-rules/SKILL.md
    decision_rules_skill = self._generate_decision_rules_skill(profile)
    if decision_rules_skill is not None:
      files["skills/decision-rules/SKILL.md"] = decision_rules_skill

    # tools/ 生成
    files["tools/project_context.json"] = self._generate_project_context(profile)
    tools = self._generate_additional_tools(profile)
    for path, content in tools:
      files[path] = content

    # Decision Engine: tools/reasoning_flow.json
    reasoning_flow_tool = self._generate_reasoning_flow_tool(profile)
    if reasoning_flow_tool is not None:
      files["tools/reasoning_flow.json"] = reasoning_flow_tool

    logger.info(
      "Package generated for agent_id=%s: %d files", agent_id, len(files)
    )
    return files

  def _generate_readme(
    self, profile: ProfileOutput, agent_id: str, display_name: str
  ) -> str:
    """README.md: セットアップガイドとエージェント概要を生成する。"""
    # persona 情報の有無で表示を切り替え
    persona = profile.persona
    has_persona = any([
      persona.nickname, persona.role, persona.industry,
    ])

    persona_section = ""
    if has_persona:
      lines = []
      if persona.nickname:
        lines.append(f"- **Nickname**: {persona.nickname}")
      if persona.role:
        lines.append(f"- **Role**: {persona.role}")
      if persona.industry:
        lines.append(f"- **Industry**: {persona.industry}")
      if persona.experience_years:
        lines.append(f"- **Experience**: {persona.experience_years}")
      persona_section = "\n".join(lines)
    else:
      persona_section = "[CUSTOMIZE] ペルソナ情報を追記してください。"

    return f"""\
# Agent Pack: {display_name}

**Agent ID**: `{agent_id}`
**Profile ID**: `{profile.profile_id}`

## Overview

このパッケージは Agent Profiler が生成したプロファイルに基づく、
パーソナライズされたエージェント構成資産です。

### Persona

{persona_section}

### Decision Style

{profile.base_os.decision_style}

## セットアップ

1. Zip を解凍
2. `skills/` フォルダの中身を以下のいずれかにコピー:
   - `.github/skills/` (GitHub Copilot)
   - `.claude/skills/` (Claude Code)
   - `.agents/skills/` (汎用)
3. `system_prompt.md` の内容をカスタムインストラクションに追記:
   - `.github/copilot-instructions.md` (GitHub Copilot)
   - `.claude/CLAUDE.md` (Claude Code)
4. `tools/project_context.json` をプロジェクトルートに配置（任意）

## ファイル構成

- `README.md` — 本ファイル
- `config.json` — エージェントメタデータ + 4軸パラメータ
- `system_prompt.md` — システムプロンプト（人格・ガードレール）
- `skills/` — Agent Skills 標準準拠のスキル定義
- `tools/` — 技術スタック情報・追加ツール
"""

  def _generate_config_json(
    self, profile: ProfileOutput, agent_id: str, display_name: str
  ) -> str:
    """config.json: メタデータ + base_os パラメータを JSON で返す。"""
    axes = profile.base_os.axes

    # skills/ と tools/ のファイルパスを収集
    skill_paths = [
      f"skills/{template['name']}/SKILL.md"
      for skill_name, template in _SKILL_TEMPLATES.items()
      if self._has_skill_keywords(profile, skill_name)
    ]
    tool_paths = ["tools/project_context.json"]
    # 追加ツールのパスも含める
    additional_tools = self._generate_additional_tools(profile)
    for path, _ in additional_tools:
      tool_paths.append(path)

    config = {
      "agent_id": agent_id,
      "profile_id": profile.profile_id,
      "display_name": display_name,
      "version": "1.0.0",
      "base_os": {
        "axes": {
          "extroverted_introverted": axes.extroverted_introverted,
          "sensing_intuition": axes.sensing_intuition,
          "thinking_feeling": axes.thinking_feeling,
          "judging_perceiving": axes.judging_perceiving,
        },
        "decision_style": profile.base_os.decision_style,
        "do_not_list": profile.base_os.do_not_list,
      },
      "skills": skill_paths,
      "tools": tool_paths,
    }

    # Decision Engine: context_adaptation をconfig に追加
    if profile.context_adaptation is not None:
      config["context_adaptation"] = {
        "modes": profile.context_adaptation.modes,
        "switch_triggers": profile.context_adaptation.switch_triggers,
      }

    return json.dumps(config, indent=2, ensure_ascii=False)

  def _generate_system_prompt_md(self, profile: ProfileOutput) -> str:
    """system_prompt.md: PromptEngine 出力を Markdown 形式で保存する。

    persona/communication_tone が欠落している場合は [CUSTOMIZE] マークを付与。
    Decision Engine データがある場合は追加セクションを挿入。
    """
    # PromptEngine でプロンプト生成
    result = self._prompt_engine.generate(profile)
    prompt_content = result.prompt

    # Decision Engine: "## Decision Framework" セクション追加
    # PromptEngine が既に Decision Framework を生成している場合はスキップ
    decision_framework_section = self._build_decision_framework_section(profile)
    if decision_framework_section and "## Decision Framework" not in prompt_content:
      prompt_content += "\n\n" + decision_framework_section

    # Decision Engine: "## Self-Awareness" セクション追加
    self_awareness_section = self._build_self_awareness_section(profile)
    if self_awareness_section:
      prompt_content += "\n\n" + self_awareness_section

    # communication_tone の有無を判定
    tone = profile.communication_tone
    has_tone = any([
      tone.pronoun, tone.formality, tone.text_style,
      tone.emotion_level, tone.humor, tone.response_length,
    ])

    # persona の有無を判定
    persona = profile.persona
    has_persona = any([
      persona.nickname, persona.role, persona.industry,
    ])

    # [CUSTOMIZE] マーク付与
    if not has_tone:
      # Communication Tone セクションが空の場合、プロンプトの末尾に追記
      prompt_content += "\n\n## Communication Tone\n\n[CUSTOMIZE] "
      prompt_content += "コミュニケーションスタイルを設定してください。"

    if not has_persona:
      prompt_content += "\n\n## Persona\n\n[CUSTOMIZE] "
      prompt_content += "ペルソナ情報（ニックネーム・役割・業界）を設定してください。"

    return prompt_content

  def _generate_skills(
    self, profile: ProfileOutput
  ) -> list[tuple[str, str]]:
    """semantic_contexts からスキルキーワードを検出し、SKILL.md を生成する。

    Agent Skills 標準準拠: skills/{skill-name}/SKILL.md の構造で出力。

    Returns:
      [("skills/reflection-wall/SKILL.md", content), ...]
    """
    # 検出済みスキルを重複なく収集
    detected_skills: set[str] = set()
    combined_text = " ".join(
      f"{k} {v}" for k, v in profile.semantic_contexts.items()
    ).lower()

    for keyword, skill_name in SKILL_KEYWORDS.items():
      if keyword.lower() in combined_text:
        detected_skills.add(skill_name)

    # SKILL.md 生成
    results: list[tuple[str, str]] = []
    for skill_name in sorted(detected_skills):
      template = _SKILL_TEMPLATES.get(skill_name)
      if template is None:
        continue

      # SKILL.md を YAML frontmatter + body で構築
      skill_md = self._build_skill_md(
        template, profile.profile_id, profile
      )
      path = f"skills/{template['name']}/SKILL.md"
      results.append((path, skill_md))

    return results

  def _build_skill_md(
    self,
    template: dict[str, str],
    profile_id: str,
    profile: ProfileOutput,
  ) -> str:
    """Agent Skills 標準に準拠した SKILL.md を構築する。"""
    # do_not_list からガードレール追記
    guardrails = "\n".join(
      f"- {item}" for item in profile.base_os.do_not_list
    )

    frontmatter = (
      f"---\n"
      f"name: {template['name']}\n"
      f"description: {template['description']}\n"
      f"metadata:\n"
      f"  generated-by: agent-profiler\n"
      f"  profile-id: {profile_id}\n"
      f"  version: \"1.0\"\n"
      f"---\n"
    )

    body = template["body"]

    # ガードレールセクション追記（Base OS から）
    additional = (
      f"\n## Agent-Specific Guardrails\n\n"
      f"The following actions are prohibited for this agent:\n"
      f"{guardrails}\n"
    )

    return frontmatter + "\n" + body + additional

  def _has_skill_keywords(
    self, profile: ProfileOutput, skill_name: str
  ) -> bool:
    """指定スキルに対応するキーワードが semantic_contexts に含まれるか判定。"""
    combined_text = " ".join(
      f"{k} {v}" for k, v in profile.semantic_contexts.items()
    ).lower()

    for keyword, mapped_skill in SKILL_KEYWORDS.items():
      if mapped_skill == skill_name and keyword.lower() in combined_text:
        return True
    return False

  def _generate_project_context(self, profile: ProfileOutput) -> str:
    """tools/project_context.json: lexical_tags から技術スタックを抽出する。"""
    tech_stack: list[str] = []
    methodologies: list[str] = []

    # 既知の技術識別子とマッチ
    for tag in profile.lexical_tags:
      tag_lower = tag.lower()
      if tag_lower in TECH_IDENTIFIERS:
        tech_stack.append(TECH_IDENTIFIERS[tag_lower])

    # メソドロジー系キーワード
    methodology_keywords = [
      "agile", "scrum", "ci/cd", "devops", "tdd", "bdd",
      "kanban", "waterfall", "pair programming",
    ]
    for tag in profile.lexical_tags:
      tag_lower = tag.lower()
      if tag_lower in methodology_keywords:
        methodologies.append(tag_lower)

    context = {
      "tech_stack": sorted(set(tech_stack)),
      "methodologies": sorted(set(methodologies)),
      "all_tags_count": len(profile.lexical_tags),
    }

    return json.dumps(context, indent=2, ensure_ascii=False)

  def _generate_additional_tools(
    self, profile: ProfileOutput
  ) -> list[tuple[str, str]]:
    """lexical_tags から追加ツールファイルを生成する。

    技術スタックに基づく workflow/linting ツールスキーマを生成。

    Returns:
      [(path, content), ...]
    """
    results: list[tuple[str, str]] = []
    tech_stack: set[str] = set()

    for tag in profile.lexical_tags:
      tag_lower = tag.lower()
      if tag_lower in TECH_IDENTIFIERS:
        tech_stack.add(TECH_IDENTIFIERS[tag_lower])

    # Docker 検出時: docker-compose ツールスキーマ
    if "docker" in tech_stack:
      tool = {
        "name": "docker-workflow",
        "description": "Docker container management workflow",
        "commands": {
          "build": "docker compose build",
          "up": "docker compose up -d",
          "down": "docker compose down",
          "logs": "docker compose logs -f",
        },
      }
      results.append((
        "tools/docker_workflow.json",
        json.dumps(tool, indent=2, ensure_ascii=False),
      ))

    # MCP 検出時: MCP 設定テンプレート
    if "mcp" in tech_stack:
      tool = {
        "name": "mcp-config",
        "description": "Model Context Protocol server configuration",
        "transport": "stdio",
        "servers": [],
      }
      results.append((
        "tools/mcp_config.json",
        json.dumps(tool, indent=2, ensure_ascii=False),
      ))

    return results

  def _build_decision_framework_section(
    self, profile: ProfileOutput
  ) -> str | None:
    """system_prompt.md 用の Decision Framework セクションを構築する。

    decision_model が無い場合は None を返す。
    """
    if profile.decision_model is None:
      return None

    dm = profile.decision_model
    lines = ["## Decision Framework", ""]

    # priorities を weight 降順でリスト
    if dm.priority_weights:
      sorted_priorities = sorted(
        dm.priority_weights.items(),
        key=lambda x: x[1],
        reverse=True,
      )
      for name, weight in sorted_priorities:
        lines.append(f"- {name} (weight: {weight})")
    elif dm.priorities:
      for p in dm.priorities:
        lines.append(f"- {p}")

    # tradeoff_tendencies
    if dm.tradeoff_tendencies:
      lines.append("")
      lines.append("### Tradeoff Tendencies")
      for pair, score in dm.tradeoff_tendencies.items():
        lines.append(f"- {pair}: {score}")

    return "\n".join(lines)

  def _build_self_awareness_section(
    self, profile: ProfileOutput
  ) -> str | None:
    """system_prompt.md 用の Self-Awareness セクションを構築する。

    failure_patterns が無い場合は None を返す。
    全4サブカテゴリ（degradation_triggers, procrastination_patterns,
    overconfidence_conditions, recurring_mistakes）をカテゴリ別に列挙。
    """
    if profile.failure_patterns is None:
      return None

    fp = profile.failure_patterns
    # サブカテゴリが全て空の場合もスキップ
    if not any([
      fp.degradation_triggers,
      fp.procrastination_patterns,
      fp.overconfidence_conditions,
      fp.recurring_mistakes,
    ]):
      return None

    lines = ["## Self-Awareness", ""]

    if fp.degradation_triggers:
      lines.append("### Degradation Triggers")
      for trigger in fp.degradation_triggers:
        lines.append(f"- ⚠️ {trigger}")
      lines.append("")

    if fp.procrastination_patterns:
      lines.append("### Procrastination Patterns")
      for pattern in fp.procrastination_patterns:
        lines.append(f"- 🕐 {pattern}")
      lines.append("")

    if fp.overconfidence_conditions:
      lines.append("### Overconfidence Conditions")
      for condition in fp.overconfidence_conditions:
        lines.append(f"- 🔴 {condition}")
      lines.append("")

    if fp.recurring_mistakes:
      lines.append("### Recurring Mistakes")
      for mistake in fp.recurring_mistakes:
        lines.append(f"- 🔄 {mistake}")
      lines.append("")

    return "\n".join(lines).rstrip()

  def _generate_decision_rules_skill(
    self, profile: ProfileOutput
  ) -> str | None:
    """skills/decision-rules/SKILL.md を生成する。

    decision_model が無い場合は None を返す（後方互換性）。
    YAML frontmatter + Escalation Rules + Auto-Approve Scope + Tradeoff Tendencies。
    """
    if profile.decision_model is None:
      return None

    dm = profile.decision_model

    # YAML frontmatter（既存 SKILL.md と同じフォーマット）
    frontmatter = (
      "---\n"
      "name: decision-rules\n"
      "description: Defines escalation rules, auto-approve scope, "
      "and tradeoff tendencies for autonomous decision-making. "
      "Use when determining whether to act autonomously or escalate "
      "to the user for approval.\n"
      "metadata:\n"
      f"  generated-by: agent-profiler\n"
      f"  profile-id: {profile.profile_id}\n"
      "  version: \"1.0\"\n"
      "---\n"
    )

    body_lines = [
      "",
      "# Decision Rules Skill",
      "",
      "## When to use",
      "- Agent needs to decide whether to act autonomously or escalate",
      "- Agent encounters a tradeoff scenario",
      "- Agent needs to determine appropriate scope of action",
      "",
    ]

    # Escalation Rules
    body_lines.append("## Escalation Rules")
    body_lines.append("")
    if dm.escalation_rules:
      for rule in dm.escalation_rules:
        body_lines.append(f"- {rule}")
    else:
      body_lines.append("- No escalation rules defined")
    body_lines.append("")

    # Auto-Approve Scope
    body_lines.append("## Auto-Approve Scope")
    body_lines.append("")
    if dm.auto_approve_scope:
      for scope in dm.auto_approve_scope:
        body_lines.append(f"- {scope}")
    else:
      body_lines.append("- No auto-approve scope defined")
    body_lines.append("")

    # Tradeoff Tendencies
    body_lines.append("## Tradeoff Tendencies")
    body_lines.append("")
    if dm.tradeoff_tendencies:
      body_lines.append("| Dimension | Score | Interpretation |")
      body_lines.append("|-----------|-------|----------------|")
      for pair, score in dm.tradeoff_tendencies.items():
        # スコアの解釈: 0.0-0.3=前者寄り, 0.4-0.6=バランス, 0.7-1.0=後者寄り
        if score <= 0.3:
          interpretation = "Leans toward first value"
        elif score >= 0.7:
          interpretation = "Leans toward second value"
        else:
          interpretation = "Balanced"
        body_lines.append(f"| {pair} | {score} | {interpretation} |")
    else:
      body_lines.append("- No tradeoff tendencies defined")
    body_lines.append("")

    return frontmatter + "\n".join(body_lines)

  def _generate_reasoning_flow_tool(
    self, profile: ProfileOutput
  ) -> str | None:
    """tools/reasoning_flow.json を生成する。

    reasoning_flow が無い場合は None を返す（後方互換性）。
    UTF-8, 2-space indent JSON。
    """
    if profile.reasoning_flow is None:
      return None

    rf = profile.reasoning_flow
    data = {
      "default_steps": rf.default_steps,
      "verification_method": rf.verification_method,
      "learning_style": rf.learning_style,
    }

    return json.dumps(data, indent=2, ensure_ascii=False)

  def build_zip(
    self, profile: ProfileOutput, agent_id: str, display_name: str
  ) -> bytes:
    """全ファイルを ZIP に圧縮してバイト列で返す。"""
    files = self.generate(profile, agent_id, display_name)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
      for path, content in sorted(files.items()):
        zf.writestr(path, content)
    return buffer.getvalue()
