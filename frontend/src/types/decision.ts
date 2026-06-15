/**
 * Decision Engine TypeScript 型定義
 * Backend の Pydantic モデルに対応するフロントエンド型
 */

/** 3層回答構造 */
export interface ThreeLayerAnswer {
  raw: {
    question_id: string
    choice_id: string | null
    choice_label: string | null
    free_text: string | null
  }
  normalized: { tags: Array<{ type: string; value: string }> } | null
  policy: { rule: string } | null
}

/** 回答メタデータ */
export interface AnswerMetadata {
  permanence: 'permanent' | 'contextual'
  confidence: number // 0.2〜1.0
  exception_note: string | null
  is_core_rule: boolean
  ambiguity: number
}

/** フィードバック送信ペイロード */
export interface FeedbackPayload {
  agent_id: string
  thread_id: string
  turn_id: string
  feedback_type: 'approve' | 'reject'
  user_correction?: string
}

/** フィードバックレコード */
export interface FeedbackRecord {
  id: number
  agent_id: string
  thread_id: string
  turn_id: string
  feedback_type: 'approve' | 'reject'
  user_correction: string | null
  original_response: string
  created_at: string
}

/** 変更履歴エントリ */
export interface ModificationHistoryEntry {
  field_name: string
  previous_value: number
  new_value: number
  adjustment_reason: string
  feedback_count: number
  timestamp: string
}

/** Ordering 質問の選択肢 */
export interface OrderingChoice {
  id: string
  label: string
}

/** Decision Engine プロファイルセクション */
export interface DecisionEngineData {
  decision_model: {
    priorities: string[]
    priority_weights: Record<string, number>
    escalation_rules: string[]
    auto_approve_scope: string[]
    tradeoff_tendencies: Record<string, number>
  } | null
  failure_patterns: {
    degradation_triggers: string[]
    procrastination_patterns: string[]
    overconfidence_conditions: string[]
    recurring_mistakes: string[]
  } | null
  context_adaptation: {
    modes: Record<string, { tone: string; detail: string; focus: string }>
    switch_triggers: Record<string, string[]>
  } | null
  reasoning_flow: {
    default_steps: string[]
    verification_method: string
    learning_style: string
  } | null
}

/** フィードバック一覧レスポンス */
export interface FeedbackListResponse {
  items: FeedbackRecord[]
  total: number
  limit: number
  offset: number
}

/** フィードバック送信レスポンス */
export interface FeedbackResponse {
  feedback_id: number
  created_at: string
}
