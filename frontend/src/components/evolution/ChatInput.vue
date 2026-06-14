<script setup lang="ts">
/**
 * ChatInput コンポーネント
 * メッセージ入力 + 送信ボタンを提供する。
 * Enter で送信、Shift+Enter で改行。
 * Validates: Requirements 21.2, 21.3, 21.5
 */

import { ref } from 'vue'

const emit = defineEmits<{
  (e: 'send', message: string): void
}>()

const props = defineProps<{
  disabled?: boolean
}>()

const input = ref('')

function send() {
  const msg = input.value.trim()
  if (!msg || props.disabled) return
  emit('send', msg)
  input.value = ''
}

function handleKeydown(event: KeyboardEvent) {
  // IME コンポジション中（日本語変換確定など）は送信しない
  if (event.isComposing || event.keyCode === 229) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}
</script>

<template>
  <div class="chat-input">
    <textarea
      v-model="input"
      placeholder="メッセージを入力..."
      :disabled="disabled"
      @keydown="handleKeydown"
      rows="2"
      aria-label="チャットメッセージ入力"
    ></textarea>
    <button
      @click="send"
      :disabled="disabled || !input.trim()"
      aria-label="メッセージ送信"
    >
      送信
    </button>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid #e5e7eb;
  background-color: #fff;
}

.chat-input textarea {
  flex: 1;
  resize: none;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  font-family: inherit;
  line-height: 1.5;
  outline: none;
  transition: border-color 0.2s;
}

.chat-input textarea:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.chat-input textarea:disabled {
  background-color: #f9fafb;
  cursor: not-allowed;
}

.chat-input button {
  align-self: flex-end;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 0.5rem;
  background-color: #3b82f6;
  color: #fff;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.chat-input button:hover:not(:disabled) {
  background-color: #2563eb;
}

.chat-input button:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.chat-input button:focus-visible {
  box-shadow: 0 0 0 2px #3b82f6;
}
</style>
