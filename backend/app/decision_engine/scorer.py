"""Decision Engine スコアリングエンジン

Mapping Dictionary を参照し、各質問カテゴリの回答から
Priority_Weight / Tradeoff_Tendency / Failure Pattern /
Context Adaptation のスコアリングを行う。
"""

from app.models.mapping import MappingEntry
from app.services.data_loader import MappingDictionaryLoader


class MappingNotFoundError(Exception):
  """マッピング辞書にエントリが存在しない場合の例外"""

  def __init__(self, question_id: str, choice_id: str):
    self.question_id = question_id
    self.choice_id = choice_id
    super().__init__(f"No mapping found for ({question_id}, {choice_id})")


class DecisionScorer:
  """意思決定スコアリングエンジン

  Mapping Dictionary を参照し、各質問カテゴリの回答から
  Priority_Weight / Tradeoff_Tendency を計算する。
  既存 ScoringEngine と同パターンだが、出力が4軸ではなく
  優先度重み・トレードオフスコアである点が異なる。
  """

  def __init__(self, mapping_loader: MappingDictionaryLoader):
    self._mapping_loader = mapping_loader
    self._lookup: dict[tuple[str, str], MappingEntry] = {}
    self._rebuild_lookup()

  def _rebuild_lookup(self) -> None:
    """Mapping Dictionary からルックアップ辞書を構築する"""
    mapping_dict = self._mapping_loader.get()
    self._lookup = {
      (e.question_id, e.choice_id): e for e in mapping_dict.mappings
    }

  def _get_entry(self, question_id: str, choice_id: str) -> MappingEntry:
    """エントリを取得し、存在しない場合は例外を送出する"""
    entry = self._lookup.get((question_id, choice_id))
    if entry is None:
      raise MappingNotFoundError(question_id, choice_id)
    return entry

  def score_decision_model(
    self, question_id: str, choice_id: str
  ) -> dict[str, int]:
    """decision_model 回答のスコアを算出する

    Mapping Dictionary の priority_labels と weights を参照し、
    priority_label → weight_increment のマッピングを返す。

    Returns:
      priority_label → weight_increment のマッピング

    Raises:
      MappingNotFoundError: question_id + choice_id の組み合わせが辞書にない場合
    """
    entry = self._get_entry(question_id, choice_id)
    # priority_labels[i] → weights[priority_labels[i]] のマッピングを構築
    if entry.priority_labels is None or entry.weights is None:
      raise MappingNotFoundError(question_id, choice_id)
    return {
      label: entry.weights[label]
      for label in entry.priority_labels
      if label in entry.weights
    }

  def score_tradeoff(
    self, question_id: str, choice_id: str
  ) -> tuple[str, float]:
    """tradeoff_scenarios 回答のスコアを算出する

    Returns:
      (conflict_pair_name, tendency_score)

    Raises:
      MappingNotFoundError: マッピングが存在しない場合
    """
    entry = self._get_entry(question_id, choice_id)
    if entry.conflict_pair is None or entry.tendency_score is None:
      raise MappingNotFoundError(question_id, choice_id)
    return (entry.conflict_pair, entry.tendency_score)

  def score_failure_pattern(
    self, question_id: str, choice_id: str
  ) -> tuple[str, str]:
    """failure_patterns 回答を分類する

    Returns:
      (subcategory, label_string)

    Raises:
      MappingNotFoundError: マッピングが存在しない場合
    """
    entry = self._get_entry(question_id, choice_id)
    if entry.subcategory is None or entry.label is None:
      raise MappingNotFoundError(question_id, choice_id)
    return (entry.subcategory, entry.label)

  def score_context_adaptation(
    self, question_id: str, choice_id: str
  ) -> dict[str, dict[str, str]]:
    """context_adaptation 回答からモード設定を導出する

    Returns:
      {mode_name: {tone, detail, focus}}

    Raises:
      MappingNotFoundError: マッピングが存在しない場合
    """
    entry = self._get_entry(question_id, choice_id)
    if entry.mode_name is None or entry.mode_config is None:
      raise MappingNotFoundError(question_id, choice_id)
    return {
      entry.mode_name: {
        "tone": entry.mode_config.tone,
        "detail": entry.mode_config.detail,
        "focus": entry.mode_config.focus,
      }
    }

  def normalize_weights(
    self, accumulated: dict[str, int]
  ) -> dict[str, float]:
    """累積重みを 0.0〜1.0 に正規化する

    formula: (value - min) / (max - min), 小数点2桁丸め
    少なくとも1つのエントリが 1.0 になることを保証する。
    全値が同一の場合は全て 1.0 を返す。
    空辞書の場合は空辞書を返す。
    """
    if not accumulated:
      return {}
    min_val = min(accumulated.values())
    max_val = max(accumulated.values())
    # 全値が同一 → 全て 1.0
    if max_val == min_val:
      return {k: 1.0 for k in accumulated}
    return {
      k: round((v - min_val) / (max_val - min_val), 2)
      for k, v in accumulated.items()
    }
