"""ポリシールールの優先順位集約"""

from dataclasses import dataclass


@dataclass
class RuleHierarchy:
  """ルール優先順位体系

  core_invariants: is_core_rule=True AND confidence>=0.8 AND permanence="permanent"
  context_rules: confidence>=0.5 AND is_core_rule=False AND no condition_tag
  exceptions: has condition_tag in normalization_tags
  preferences: everything else
  """

  core_invariants: list[dict]
  context_rules: list[dict]
  exceptions: list[dict]
  preferences: list[dict]


class RuleAggregator:
  """ポリシールールの優先順位集約

  AnswerPipeline.get_all_policies() の出力を受け取り、
  4層ヒエラルキーに分類する。
  """

  MAX_CORE_INVARIANTS = 10

  def aggregate(self, policies: list[dict], max_core: int = 10) -> RuleHierarchy:
    """全ポリシーを Rule Hierarchy に集約する

    Args:
      policies: [{question_id, rule, confidence, is_core, permanence, normalization_tags}, ...]
      max_core: core_invariants の最大数

    Classification logic:
    1. core_invariants: is_core=True AND confidence>=0.8 AND permanence="permanent"
       - Limited to max_core entries (sorted by confidence desc)
    2. exceptions: any policy with condition_tag in normalization_tags
    3. context_rules: confidence>=0.5 AND NOT core AND NOT exception
    4. preferences: everything else
    """
    core: list[dict] = []
    context: list[dict] = []
    exceptions: list[dict] = []
    preferences: list[dict] = []

    for policy in policies:
      classification = self._classify_rule(policy)
      if classification == "core_invariants":
        core.append(policy)
      elif classification == "exceptions":
        exceptions.append(policy)
      elif classification == "context_rules":
        context.append(policy)
      else:
        preferences.append(policy)

    # core_invariants: confidence降順でソートし、max_core件に制限
    core.sort(key=lambda p: p.get("confidence", 0), reverse=True)
    if len(core) > max_core:
      # 超過分を context_rules に降格
      overflow = core[max_core:]
      core = core[:max_core]
      context.extend(overflow)

    return RuleHierarchy(
      core_invariants=core,
      context_rules=context,
      exceptions=exceptions,
      preferences=preferences,
    )

  def _classify_rule(self, policy: dict) -> str:
    """単一ルールの分類先を決定する

    Priority order:
    1. Check if it has condition_tag → exceptions
    2. Check core_invariant conditions → core_invariants
    3. Check context_rules conditions → context_rules
    4. Otherwise → preferences
    """
    tags = policy.get("normalization_tags", [])

    # condition_tag があれば例外ルール
    has_condition = any(
      isinstance(t, dict) and t.get("type") == "condition_tag"
      for t in tags
    )
    if has_condition:
      return "exceptions"

    # core_invariant 条件: is_core=True AND confidence>=0.8 AND permanence="permanent"
    is_core = policy.get("is_core", False)
    confidence = policy.get("confidence", 0.0)
    permanence = policy.get("permanence", "permanent")

    if is_core and confidence >= 0.8 and permanence == "permanent":
      return "core_invariants"

    # context_rules 条件: confidence>=0.5
    if confidence >= 0.5:
      return "context_rules"

    return "preferences"
