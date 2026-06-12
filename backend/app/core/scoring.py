"""スコアリングエンジン: 1問多軸ブレンドスコアリングの中核ロジック"""

from app.models.mapping import MappingDictionary
from app.models.scores import AxisScores


class MappingNotFoundError(Exception):
  """指定された question_id + choice_id の組み合わせが
  Mapping Dictionary に存在しない場合に発生するエラー。
  """

  def __init__(self, question_id: str, choice_id: str) -> None:
    self.question_id = question_id
    self.choice_id = choice_id
    super().__init__(
      f"Mapping not found: question_id='{question_id}', choice_id='{choice_id}'"
    )


class ScoringEngine:
  """1問多軸ブレンドスコアリングの中核ロジック

  Mapping Dictionary を受け取り、(question_id, choice_id) ペアから
  4軸スコアベクトルを検索・累積加算する純粋関数群を提供する。
  """

  def __init__(self, mapping_dict: MappingDictionary) -> None:
    # O(1) ルックアップのため (question_id, choice_id) -> MappingScores の辞書を構築
    self._lookup: dict[tuple[str, str], tuple[int, int, int, int]] = {}
    for entry in mapping_dict.mappings:
      key = (entry.question_id, entry.choice_id)
      self._lookup[key] = (
        entry.scores.extroverted_introverted,
        entry.scores.sensing_intuition,
        entry.scores.thinking_feeling,
        entry.scores.judging_perceiving,
      )

  def apply_score(
    self, session_scores: AxisScores, question_id: str, choice_id: str
  ) -> AxisScores:
    """選択肢に対応するスコアベクトルを累積加算した新しい AxisScores を返す。

    Args:
      session_scores: 現在のセッション累積スコア
      question_id: 質問ID
      choice_id: 選択肢ID

    Returns:
      加算後の新しい AxisScores（元のオブジェクトは変更しない）

    Raises:
      MappingNotFoundError: 指定の組み合わせがマッピングに存在しない場合
    """
    key = (question_id, choice_id)
    scores = self._lookup.get(key)
    if scores is None:
      raise MappingNotFoundError(question_id, choice_id)

    ei, sn, tf, jp = scores
    return AxisScores(
      extroverted_introverted=session_scores.extroverted_introverted + ei,
      sensing_intuition=session_scores.sensing_intuition + sn,
      thinking_feeling=session_scores.thinking_feeling + tf,
      judging_perceiving=session_scores.judging_perceiving + jp,
    )

  def apply_neutral(self, session_scores: AxisScores) -> AxisScores:
    """Other選択時のニュートラルスコア適用（identity operation）。

    全軸0を加算する = スコア不変。元の AxisScores をそのまま返す。

    Args:
      session_scores: 現在のセッション累積スコア

    Returns:
      同一の AxisScores（スコア不変）
    """
    return session_scores

  def apply_llm_scores(
    self,
    session_scores: AxisScores,
    ei: int,
    sn: int,
    tf: int,
    jp: int,
  ) -> AxisScores:
    """LLMが推定した4軸スコアを累積加算する。

    Args:
      session_scores: 現在のセッション累積スコア
      ei, sn, tf, jp: LLMが推定した各軸のスコア（-10〜+10）

    Returns:
      加算後の新しい AxisScores
    """
    return AxisScores(
      extroverted_introverted=session_scores.extroverted_introverted + ei,
      sensing_intuition=session_scores.sensing_intuition + sn,
      thinking_feeling=session_scores.thinking_feeling + tf,
      judging_perceiving=session_scores.judging_perceiving + jp,
    )
