/**
 * Agent CRUD composable
 * Requirements: 21.1 - 分身プロファイル管理フロントエンド
 *
 * リアクティブなエージェント一覧状態管理と
 * Agent Manager API へのクライアント操作を提供する。
 */

import { ref } from 'vue'
import { apiFetch } from '@/composables/useApi'

export interface Agent {
  agent_id: string
  profile_id: string
  display_name: string
  created_at: string
  is_active: boolean
}

export function useAgents() {
  const agents = ref<Agent[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  /** 指定 profile_id に紐づくアクティブエージェント一覧を取得 */
  async function listAgents(profileId: string) {
    loading.value = true
    error.value = null
    try {
      agents.value = await apiFetch<Agent[]>(
        `/v1/evolution/agents?profile_id=${profileId}`,
      )
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  /** 新規エージェントを作成しローカル状態に追加 */
  async function createAgent(
    profileId: string,
    displayName: string,
  ): Promise<Agent | null> {
    loading.value = true
    error.value = null
    try {
      const agent = await apiFetch<Agent>('/v1/evolution/agents', {
        method: 'POST',
        body: JSON.stringify({ profile_id: profileId, display_name: displayName }),
      })
      agents.value.push(agent)
      return agent
    } catch (e: any) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  /** エージェントを論理削除しローカル状態から除外 */
  async function deleteAgent(agentId: string) {
    try {
      await apiFetch(`/v1/evolution/agents/${agentId}`, { method: 'DELETE' })
      agents.value = agents.value.filter((a) => a.agent_id !== agentId)
    } catch (e: any) {
      error.value = e.message
    }
  }

  return { agents, loading, error, listAgents, createAgent, deleteAgent }
}
