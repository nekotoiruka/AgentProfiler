/**
 * Decision Engine サーベイ composable
 * Requirements: 1.2, 2.2, 3.2, 4.2, 5.5
 *
 * Decision Engine 質問の回答送信・メタデータ管理を提供する。
 * 既存 apiFetch パターンを利用し、リトライ・エラーハンドリングを統一。
 */

import { ref } from 'vue'
import { apiFetch } from '@/composables/useApi'
import type { AnswerMetadata } from '@/types/decision'

export function useDecisionSurvey(sessionId: string) {
  const loading = ref(false)
  const error = ref<string | null>(null)

  /**
   * 回答を送信する
   * single_select / binary_choice / free-text に対応
   */
  async function submitAnswer(
    questionId: string,
    choiceId: string | null,
    text: string | null,
    metadata?: AnswerMetadata,
  ) {
    loading.value = true
    error.value = null
    try {
      const result = await apiFetch<{ status: string }>(
        `/sessions/${sessionId}/answers`,
        {
          method: 'POST',
          body: JSON.stringify({
            question_id: questionId,
            choice_id: choiceId,
            text,
            metadata,
          }),
        },
      )
      return result
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * Ordering 質問の回答を送信する
   * 並び替え結果を JSON 文字列化して choice_id として送信
   */
  async function submitOrderingAnswer(
    questionId: string,
    orderedIds: string[],
    metadata?: AnswerMetadata,
  ) {
    return submitAnswer(questionId, JSON.stringify(orderedIds), null, metadata)
  }

  return { loading, error, submitAnswer, submitOrderingAnswer }
}
