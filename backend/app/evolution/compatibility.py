"""Compatibility Engine: 4軸パラメータに基づく相性診断・レコメンドエンジン

Cosine Similarity (類似度) と Complementarity (相補性) を
重み付け合成して最終スコアを算出し、分類・レコメンドを提供する。
"""

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)

# 4軸の名前定義
AXIS_NAMES = [
  "extroverted_introverted",
  "sensing_intuition",
  "thinking_feeling",
  "judging_perceiving",
]

# 分類 → 関係性ラベルの日本語マッピング
RELATIONSHIP_TYPE_MAP: dict[str, str] = {
  "highly_similar": "最高のブレインストーミングパートナー",
  "moderately_similar": "信頼できるビジネスパートナー",
  "complementary": "視野を広げるメンター",
  "contrasting": "建設的対立パートナー",
}

# 分類 → 推奨インタラクションモードのマッピング
INTERACTION_MODE_MAP: dict[str, str] = {
  "highly_similar": "brainstorming",
  "moderately_similar": "collaboration",
  "complementary": "mentoring",
  "contrasting": "debate",
}

# 分類 → 理由テンプレート
REASON_MAP: dict[str, str] = {
  "highly_similar": "両者は非常に似た価値観とアプローチを持ち、共鳴しやすい関係です。",
  "moderately_similar": "基本的な方向性が揃っており、安定した協力関係を構築できます。",
  "complementary": "互いの弱点を補い合える関係であり、新たな視点を得られます。",
  "contrasting": "異なるアプローチが建設的な議論を生み出し、より深い洞察に導きます。",
}


class SimilarityClassification(str, Enum):
  """相性分類の列挙型"""

  HIGHLY_SIMILAR = "highly_similar"
  MODERATELY_SIMILAR = "moderately_similar"
  COMPLEMENTARY = "complementary"
  CONTRASTING = "contrasting"


@dataclass
class CompatibilityReport:
  """相性診断レポート"""

  overall_score: float  # 0-100
  cosine_similarity: float  # 0.0-1.0
  complementarity_score: float  # 0.0-1.0
  per_axis_comparison: dict[str, dict]  # axis_name → {agent_1, agent_2, diff}
  classification: SimilarityClassification
  relationship_type: str  # 人間可読ラベル
  reason: str  # 1-2文のマッチング理由
  recommended_interaction_mode: str


@dataclass
class Recommendation:
  """レコメンド結果1件"""

  agent_id: str
  display_name: str
  score: float
  explanation: str


class CompatibilityEngine:
  """4軸パラメータに基づく相性診断・レコメンドエンジン

  Cosine Similarity (類似度) と Complementarity (相補性) を
  重み付け合成して最終スコアを算出する。
  """

  def __init__(
    self,
    similarity_weight: float = 0.6,
    complementarity_weight: float = 0.4,
  ):
    """CompatibilityEngine を初期化する。

    Args:
      similarity_weight: 類似度の重み (デフォルト 0.6)
      complementarity_weight: 相補性の重み (デフォルト 0.4)
    """
    self._sim_weight = similarity_weight
    self._comp_weight = complementarity_weight

  def compute_similarity(
    self, axes_a: list[float], axes_b: list[float]
  ) -> float:
    """4軸ベクトル間の Cosine Similarity を計算する。

    Args:
      axes_a: エージェントAの4軸スコア [0.0-1.0] × 4
      axes_b: エージェントBの4軸スコア [0.0-1.0] × 4

    Returns:
      0.0〜1.0 のコサイン類似度スコア
    """
    a = np.array(axes_a, dtype=np.float64)
    b = np.array(axes_b, dtype=np.float64)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    # ゼロベクトル対応
    if norm_a == 0 or norm_b == 0:
      return 0.0
    similarity = float(np.dot(a, b) / (norm_a * norm_b))
    # 数値誤差で 1.0 を超える場合をクリップ
    return max(0.0, min(1.0, similarity))

  def compute_complementarity(
    self, axes_a: list[float], axes_b: list[float]
  ) -> float:
    """相補性スコアを計算する。

    各軸の差の絶対値の平均を 0.0〜1.0 で返す。
    差が大きいほど相補性が高い。

    Args:
      axes_a: エージェントAの4軸スコア [0.0-1.0] × 4
      axes_b: エージェントBの4軸スコア [0.0-1.0] × 4

    Returns:
      0.0〜1.0 の相補性スコア
    """
    diffs = [abs(a - b) for a, b in zip(axes_a, axes_b)]
    return sum(diffs) / len(diffs)

  def compute_compatibility(
    self, axes_a: list[float], axes_b: list[float]
  ) -> CompatibilityReport:
    """総合相性レポートを生成する。

    final_score = (sim_weight * similarity + comp_weight * complementarity) * 100
    スケール: 0〜100

    Args:
      axes_a: エージェントAの4軸スコア [0.0-1.0] × 4
      axes_b: エージェントBの4軸スコア [0.0-1.0] × 4

    Returns:
      CompatibilityReport (総合スコア・分類・レコメンド含む)
    """
    similarity = self.compute_similarity(axes_a, axes_b)
    complementarity = self.compute_complementarity(axes_a, axes_b)
    overall = (
      self._sim_weight * similarity + self._comp_weight * complementarity
    ) * 100

    # per_axis_comparison を構築
    per_axis_comparison: dict[str, dict] = {}
    for i, axis_name in enumerate(AXIS_NAMES):
      per_axis_comparison[axis_name] = {
        "agent_1": axes_a[i],
        "agent_2": axes_b[i],
        "diff": abs(axes_a[i] - axes_b[i]),
      }

    # 分類決定
    classification = self.classify(similarity, complementarity)

    # 関係性ラベル・理由・推奨モード
    relationship_type = RELATIONSHIP_TYPE_MAP[classification.value]
    reason = REASON_MAP[classification.value]
    recommended_interaction_mode = INTERACTION_MODE_MAP[classification.value]

    return CompatibilityReport(
      overall_score=round(overall, 2),
      cosine_similarity=round(similarity, 4),
      complementarity_score=round(complementarity, 4),
      per_axis_comparison=per_axis_comparison,
      classification=classification,
      relationship_type=relationship_type,
      reason=reason,
      recommended_interaction_mode=recommended_interaction_mode,
    )

  def classify(
    self, similarity: float, complementarity: float
  ) -> SimilarityClassification:
    """類似度と相補性から分類を決定する。

    分類ルール:
    - HIGHLY_SIMILAR: similarity >= 0.9
    - MODERATELY_SIMILAR: similarity >= 0.7
    - COMPLEMENTARY: complementarity >= 0.5
    - CONTRASTING: 上記いずれにも該当しない場合

    Args:
      similarity: コサイン類似度 (0.0-1.0)
      complementarity: 相補性スコア (0.0-1.0)

    Returns:
      SimilarityClassification
    """
    if similarity >= 0.9:
      return SimilarityClassification.HIGHLY_SIMILAR
    if similarity >= 0.7:
      return SimilarityClassification.MODERATELY_SIMILAR
    if complementarity >= 0.5:
      return SimilarityClassification.COMPLEMENTARY
    return SimilarityClassification.CONTRASTING

  async def recommend(
    self,
    source_agent_id: str,
    all_agents: list[dict],
  ) -> dict[str, list[Recommendation]]:
    """レコメンドを生成する。

    source_agent_id のエージェントと他の全エージェントの相性を計算し、
    2カテゴリ × 最大3件のレコメンドを返す。

    Args:
      source_agent_id: 比較元エージェントの ID
      all_agents: [{agent_id, axes, display_name}, ...] 形式の全エージェントリスト

    Returns:
      {"most_heated_debate": [...], "business_partner": [...]}
      各カテゴリ最大3件
    """
    # ソースエージェントの axes を取得
    source_axes: list[float] | None = None
    for agent in all_agents:
      if agent["agent_id"] == source_agent_id:
        source_axes = agent["axes"]
        break

    if source_axes is None:
      logger.warning(
        "Source agent '%s' not found in all_agents", source_agent_id
      )
      return {"most_heated_debate": [], "business_partner": []}

    # 他のエージェントとの比較
    debate_candidates: list[tuple[float, Recommendation]] = []
    partner_candidates: list[tuple[float, Recommendation]] = []

    for agent in all_agents:
      if agent["agent_id"] == source_agent_id:
        continue

      axes_b = agent["axes"]
      complementarity = self.compute_complementarity(source_axes, axes_b)
      similarity = self.compute_similarity(source_axes, axes_b)

      # most_heated_debate: 相補性が高いエージェント
      debate_candidates.append((
        complementarity,
        Recommendation(
          agent_id=agent["agent_id"],
          display_name=agent["display_name"],
          score=round(complementarity * 100, 2),
          explanation=f"相補性スコア {complementarity:.2f} — 異なる視点から議論を深められます",
        ),
      ))

      # business_partner: 類似度が高いエージェント
      partner_candidates.append((
        similarity,
        Recommendation(
          agent_id=agent["agent_id"],
          display_name=agent["display_name"],
          score=round(similarity * 100, 2),
          explanation=f"類似度スコア {similarity:.2f} — 価値観が共鳴し協力しやすい関係です",
        ),
      ))

    # 降順ソートして上位3件
    debate_candidates.sort(key=lambda x: x[0], reverse=True)
    partner_candidates.sort(key=lambda x: x[0], reverse=True)

    return {
      "most_heated_debate": [rec for _, rec in debate_candidates[:3]],
      "business_partner": [rec for _, rec in partner_candidates[:3]],
    }
