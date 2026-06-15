"""Property 11: プロンプトトークン制限遵守

任意の decision engine セクション組み合わせで max_tokens を超過しないことを検証する。

**Validates: Requirements 7.6**
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.decision_engine.models import (
  ContextAdaptationOutput,
  DecisionModelOutput,
  FailurePatternsOutput,
  ReasoningFlowOutput,
)
from app.evolution.prompt_engine import PromptEngine
from app.models.profile import BaseOS, ContextLayers, Persona, CommunicationTone, ProfileOutput
from app.models.scores import NormalizedScores


def _make_profile(
  decision_model=None,
  failure_patterns=None,
  context_adaptation=None,
  reasoning_flow=None,
) -> ProfileOutput:
  return ProfileOutput(
    profile_id="prof_000001",
    persona=Persona(),
    communication_tone=CommunicationTone(),
    base_os=BaseOS(
      axes=NormalizedScores(
        extroverted_introverted=0.5,
        sensing_intuition=0.5,
        thinking_feeling=0.5,
        judging_perceiving=0.5,
      ),
      decision_style="Balanced",
      do_not_list=["test"],
    ),
    lexical_tags=["a", "b", "c", "d", "e"],
    semantic_contexts={"problem_solving": "Test"},
    context_layers=ContextLayers(),
    decision_model=decision_model,
    failure_patterns=failure_patterns,
    context_adaptation=context_adaptation,
    reasoning_flow=reasoning_flow,
  )


# Strategies for optional decision engine sections
decision_model_strategy = st.one_of(
  st.none(),
  st.just(DecisionModelOutput(
    priorities=["a", "b", "c"],
    priority_weights={"a": 1.0, "b": 0.7, "c": 0.3},
    escalation_rules=["rule1"],
    auto_approve_scope=["scope1"],
    tradeoff_tendencies={"speed_vs_quality": 0.5},
  )),
)

failure_patterns_strategy = st.one_of(
  st.none(),
  st.just(FailurePatternsOutput(
    degradation_triggers=["trigger1", "trigger2"],
    procrastination_patterns=["pattern1"],
    overconfidence_conditions=["cond1"],
    recurring_mistakes=["mistake1", "mistake2"],
  )),
)

context_adaptation_strategy = st.one_of(
  st.none(),
  st.just(ContextAdaptationOutput(
    modes={"emergency": {"tone": "direct", "detail": "minimal", "focus": "action"}},
    switch_triggers={"urgency": ["keyword1", "keyword2"]},
  )),
)

reasoning_flow_strategy = st.one_of(
  st.none(),
  st.just(ReasoningFlowOutput(
    default_steps=["step1", "step2", "step3", "step4"],
    verification_method="tests",
    learning_style="hands-on",
  )),
)


@given(
  dm=decision_model_strategy,
  fp=failure_patterns_strategy,
  ca=context_adaptation_strategy,
  rf=reasoning_flow_strategy,
  max_tokens=st.integers(min_value=200, max_value=8000),
)
@settings(max_examples=200)
def test_prompt_never_exceeds_max_tokens(dm, fp, ca, rf, max_tokens):
  """任意のセクション組み合わせ + max_tokens で超過しないこと"""
  profile = _make_profile(
    decision_model=dm,
    failure_patterns=fp,
    context_adaptation=ca,
    reasoning_flow=rf,
  )

  engine = PromptEngine(max_tokens=max_tokens)

  try:
    result = engine.generate(profile)
    assert result.token_count <= max_tokens
  except ValueError:
    # max_tokens が基本プロンプトすら収められない場合は例外OK
    pass
