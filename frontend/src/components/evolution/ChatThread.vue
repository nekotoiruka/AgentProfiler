<script setup lang="ts">
/**
 * ChatThread コンポーネント
 * チャットメッセージをスレッド形式で表示する。
 * ユーザーメッセージは右寄せ、エージェント応答は左寄せ + アバターで描画。
 * SSE ストリーミング中はタイピングインジケーターを表示する。
 * Validates: Requirements 21.2, 21.3, 21.4, 21.5, 21.6
 */

import { ref, watch, nextTick } from 'vue'
import type { ChatTurn } from './composables/useChat'

const props = defineProps<{
  messages: ChatTurn[]
  streaming: boolean
}>()

const messagesContainer = ref<HTMLElement | null>(null)

// 新しいメッセージ追加時に自動スクロール
watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  }
)

// ストリーミング中のコンテンツ更新でも最下部にスクロール
watch(
  () => props.messages[props.messages.length - 1]?.content,
  async () => {
    if (!props.streaming) return
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  }
)

/** ISO 文字列を短い時刻表示に変換する */
function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString)
    return date.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}
</script>

<template>
  <div
    ref="messagesContainer"
    class="chat-thread"
    role="log"
    aria-label="チャットメッセージ一覧"
    aria-live="polite"
  >
    <div
      v-for="msg in messages"
      :key="msg.turn_id"
      :class="['message', msg.role]"
    >
      <div v-if="msg.role === 'assistant'" class="avatar" aria-hidden="true">
        🤖
      </div>
      <div class="bubble">
        <p class="content">{{ msg.content }}</p>
        <span class="timestamp">{{ formatTime(msg.created_at) }}</span>
      </div>
    </div>
    <div v-if="streaming" class="typing-indicator" aria-label="応答生成中">
      <span></span>
      <span></span>
      <span></span>
    </div>
  </div>
</template>

<style scoped>
.chat-thread {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  overflow-y: auto;
  height: 100%;
}

.message {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  max-width: 80%;
}

/* ユーザーメッセージ: 右寄せ */
.message.user {
  flex-direction: row-reverse;
  align-self: flex-end;
}

/* エージェント応答: 左寄せ + アバター */
.message.assistant {
  flex-direction: row;
  align-self: flex-start;
}

.avatar {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background-color: #e0e7ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
}

.bubble {
  padding: 0.625rem 0.875rem;
  border-radius: 1rem;
  word-break: break-word;
}

.message.user .bubble {
  background-color: #3b82f6;
  color: #fff;
  border-bottom-right-radius: 0.25rem;
}

.message.assistant .bubble {
  background-color: #f3f4f6;
  color: #1f2937;
  border-bottom-left-radius: 0.25rem;
}

.content {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  white-space: pre-wrap;
}

.timestamp {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.6875rem;
  opacity: 0.6;
}

.message.user .timestamp {
  text-align: right;
}

/* タイピングインジケーター: 3つのアニメーションドット */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
  align-self: flex-start;
}

.typing-indicator span {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background-color: #9ca3af;
  animation: typing-bounce 1.2s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-0.375rem);
    opacity: 1;
  }
}
</style>
