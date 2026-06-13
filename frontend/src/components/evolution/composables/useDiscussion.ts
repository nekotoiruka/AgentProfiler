/**
 * Discussion SSE composable
 * Requirements: 22.3, 22.4 - マルチエージェント対話観覧シアター
 *
 * SSE ストリーミングによるターン受信、議論状態管理、プログレス計算を提供する。
 * fetch + ReadableStream を使用し、サーバーからのターンイベントを逐次パースする。
 */

import { ref, computed } from 'vue'

export interface DiscussionTurn {
  discussion_id: string
  turn_number: number
  agent_id: string
  display_name: string
  content: string
  timestamp: string
}

export function useDiscussion() {
  const turns = ref<DiscussionTurn[]>([])
  const discussionId = ref<string | null>(null)
  const streaming = ref(false)
  const error = ref<string | null>(null)
  const totalExpectedTurns = ref(0)

  /** 現在のプログレス (0–100) */
  const progress = computed(() => {
    if (totalExpectedTurns.value === 0) return 0
    return Math.round((turns.value.length / totalExpectedTurns.value) * 100)
  })

  const BASE_URL = import.meta.env.VITE_API_URL || '/api'

  /**
   * 議論を開始し、SSE ストリームでターンを受信する。
   * サーバーは各ターン生成時に data: JSON 形式で逐次配信する。
   */
  async function startDiscussion(
    agentIds: string[],
    theme: string,
    maxTurnsPerAgent: number = 10,
  ) {
    streaming.value = true
    error.value = null
    turns.value = []
    totalExpectedTurns.value = maxTurnsPerAgent * agentIds.length

    try {
      const resp = await fetch(`${BASE_URL}/v1/evolution/discussions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          agent_ids: agentIds,
          theme,
          max_turns_per_agent: maxTurnsPerAgent,
        }),
      })

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({ message: resp.statusText }))
        throw new Error(body.message || body.error || resp.statusText)
      }

      const reader = resp.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      // SSE パース: 各イベントは "\n\n" で区切られる
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const events = buffer.split('\n\n')
        buffer = events.pop() || '' // 不完全なイベントはバッファに残す

        for (const event of events) {
          if (event.startsWith('data: ')) {
            const payload = JSON.parse(event.slice(6)) as DiscussionTurn
            turns.value.push(payload)
            if (payload.discussion_id) {
              discussionId.value = payload.discussion_id
            }
          }
        }
      }
    } catch (e: any) {
      error.value = e.message
    } finally {
      streaming.value = false
    }
  }

  /** 状態をリセットして新規議論に備える */
  function reset() {
    turns.value = []
    discussionId.value = null
    streaming.value = false
    error.value = null
    totalExpectedTurns.value = 0
  }

  return {
    turns,
    discussionId,
    streaming,
    error,
    progress,
    totalExpectedTurns,
    startDiscussion,
    reset,
  }
}
