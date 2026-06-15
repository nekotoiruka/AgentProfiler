/**
 * フィードバック API composable
 * Requirements: 11.1, 11.2, 11.7
 *
 * フィードバック送信・一覧取得・変更履歴取得の API クライアント。
 * 既存 apiFetch パターンを利用し、リトライ・エラーハンドリングを統一。
 */

import { ref } from 'vue'
import { apiFetch } from '@/composables/useApi'
import type {
  FeedbackPayload,
  FeedbackResponse,
  FeedbackListResponse,
  ModificationHistoryEntry,
} from '@/types/decision'

export function useFeedback() {
  const loading = ref(false)
  const error = ref<string | null>(null)

  /** フィードバックを送信する（approve / reject） */
  async function submitFeedback(payload: FeedbackPayload): Promise<FeedbackResponse> {
    loading.value = true
    error.value = null
    try {
      const result = await apiFetch<FeedbackResponse>('/feedback', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      return result
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      throw e
    } finally {
      loading.value = false
    }
  }

  /** エージェントのフィードバック一覧を取得する（ページネーション付き） */
  async function getFeedbackList(
    agentId: string,
    limit = 20,
    offset = 0,
  ): Promise<FeedbackListResponse> {
    const result = await apiFetch<FeedbackListResponse>(
      `/feedback/${agentId}?limit=${limit}&offset=${offset}`,
    )
    return result
  }

  /** プロファイルの重み変更履歴を取得する */
  async function getModificationHistory(
    profileId: string,
  ): Promise<ModificationHistoryEntry[]> {
    const data = await apiFetch<{ items: ModificationHistoryEntry[] }>(
      `/profiles/${profileId}/modification-history`,
    )
    return data.items
  }

  return { loading, error, submitFeedback, getFeedbackList, getModificationHistory }
}
