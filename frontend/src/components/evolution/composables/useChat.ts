/**
 * Chat API SSE クライアント composable
 * Requirements: 21.4 - SSEストリーミングによるリアルタイムチャット
 *
 * メッセージ送信（通常/ストリーミング）、スレッド切替、会話履歴管理を提供する。
 */

import { ref } from 'vue'
import { apiFetch } from '@/composables/useApi'

export interface ChatTurn {
  turn_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatResponse {
  thread_id: string
  agent_id: string
  response: string
  created_at: string
}

export function useChat() {
  const messages = ref<ChatTurn[]>([])
  const threadId = ref<string | null>(null)
  const loading = ref(false)
  const streaming = ref(false)
  const error = ref<string | null>(null)

  const BASE_URL = import.meta.env.VITE_API_URL || '/api'

  /**
   * 通常モードでメッセージ送信（非ストリーミング）
   * レスポンス全体を受け取ってから描画する。
   */
  async function sendMessage(agentId: string, message: string) {
    loading.value = true
    error.value = null

    // ユーザーメッセージを即時表示
    messages.value.push({
      turn_id: crypto.randomUUID(),
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
    })

    try {
      const resp = await apiFetch<ChatResponse>(
        `/v1/evolution/agents/${agentId}/chat`,
        {
          method: 'POST',
          body: JSON.stringify({ message, thread_id: threadId.value }),
        }
      )
      threadId.value = resp.thread_id
      messages.value.push({
        turn_id: crypto.randomUUID(),
        role: 'assistant',
        content: resp.response,
        created_at: resp.created_at,
      })
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  /**
   * SSE ストリーミングモードでメッセージ送信
   * Accept: text/event-stream ヘッダーで SSE レスポンスを要求し、
   * ReadableStream からチャンクを逐次読み取りアシスタント応答をリアルタイム更新する。
   */
  async function sendMessageStreaming(agentId: string, message: string) {
    streaming.value = true
    error.value = null

    messages.value.push({
      turn_id: crypto.randomUUID(),
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
    })

    try {
      const resp = await fetch(
        `${BASE_URL}/v1/evolution/agents/${agentId}/chat`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          },
          body: JSON.stringify({ message, thread_id: threadId.value }),
        }
      )

      if (!resp.ok) {
        throw new Error(`Chat request failed: ${resp.status} ${resp.statusText}`)
      }

      const reader = resp.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let assistantContent = ''
      const assistantTurn: ChatTurn = {
        turn_id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
      }
      messages.value.push(assistantTurn)

      // SSE チャンクを逐次パースしてリアルタイム描画
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value, { stream: true })
        // SSE フォーマット: "data: {...}\n\n"
        const lines = text.split('\n')
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const payload = JSON.parse(line.slice(6))
            assistantContent += payload.content || ''
            assistantTurn.content = assistantContent
            if (payload.thread_id) threadId.value = payload.thread_id
          }
        }
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      streaming.value = false
    }
  }

  /**
   * 指定スレッドの会話履歴をロード
   */
  async function loadHistory(agentId: string, tid: string) {
    loading.value = true
    error.value = null

    try {
      messages.value = await apiFetch<ChatTurn[]>(
        `/v1/evolution/agents/${agentId}/chat/${tid}`
      )
      threadId.value = tid
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  /**
   * スレッド切替（メッセージをクリアし新しい thread_id をセット）
   */
  function switchThread(newThreadId: string | null) {
    threadId.value = newThreadId
    messages.value = []
  }

  return {
    messages,
    threadId,
    loading,
    streaming,
    error,
    sendMessage,
    sendMessageStreaming,
    loadHistory,
    switchThread,
  }
}
