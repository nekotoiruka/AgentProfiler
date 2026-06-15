"""Property 16: Discussion 対立指示の生成条件

tradeoff_tendencies 差の絶対値 >= 0.4 の場合に立場維持指示が含まれることを検証する。

**Validates: Requirements 10.3**
"""

from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from app.decision_engine.models import DecisionModelOutput
from app.evolution.discussion_engine import DiscussionEngine
from app.evolution.context_layer_manager import ContextLayerManager
from app.evolution.routing_engine import RoutingEngine
from app.evolution.agent_manager import AgentManager
from app.models.profile import ProfileOutput


DIMENSIONS = [
  "speed_vs_quality", "innovation_vs_stability", "individual_vs_team",
  "short_term_vs_long_term", "perfection_vs_progress",
  "autonomy_vs_consensus", "breadth_vs_depth", "process_vs_outcome",
]


def _make_engine():
  clm = MagicMock(spec=ContextLayerManager)
  mgr = MagicMock(spec=AgentManager)
  routing = MagicMock(spec=RoutingEngine)
  return DiscussionEngine(
    db_path=":memory:", routing_engine=routing,
    context_layer_manager=clm, agent_manager=mgr,
  )


def _make_profile_with_tendencies(tendencies: dict[str, float]) -> MagicMock:
  profile = MagicMock(spec=ProfileOutput)
  dm = DecisionModelOutput(
    priorities=["test"],
    priority_weights={"test": 1.0},
    escalation_rules=[],
    auto_approve_scope=[],
    tradeoff_tendencies=tendencies,
  )
  profile.decision_model = dm
  profile.reasoning_flow = None
  return profile


@given(
  dimension=st.sampled_from(DIMENSIONS),
  agent_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
  other_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)
@settings(max_examples=300)
def test_conflict_directive_generation(dimension, agent_score, other_score):
  """差 >= 0.4 で指示が生成される、差 < 0.4 で生成されない"""
  engine = _make_engine()

  agent_profile = _make_profile_with_tendencies({dimension: agent_score})
  other_profile = _make_profile_with_tendencies({dimension: other_score})

  directives = engine._build_conflict_directives(agent_profile, [other_profile])

  diff = round(abs(agent_score - other_score), 2)

  if diff >= 0.4:
    # 指示が生成されるべき
    assert any(dimension in d for d in directives), (
      f"Expected directive for {dimension} (diff={diff}), got {directives}"
    )
  else:
    # 指示が生成されないべき
    assert not any(dimension in d for d in directives), (
      f"Unexpected directive for {dimension} (diff={diff}), got {directives}"
    )
