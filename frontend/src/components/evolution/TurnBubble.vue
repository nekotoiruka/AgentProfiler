<script setup lang="ts">
/**
 * TurnBubble.vue
 * Requirements: 22.3 - マルチエージェント対話観覧シアター
 *
 * 各エージェントの発話をアバター + カラーコーディング + display_name で
 * 視覚的に区別するスピーチバブルコンポーネント。
 */

import type { DiscussionTurn } from './composables/useDiscussion'

const props = defineProps<{
  turn: DiscussionTurn
  colorIndex: number
}>()

// エージェント色パレット（最大6人分）
const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']

function getColor(): string {
  return COLORS[props.colorIndex % COLORS.length]
}
</script>

<template>
  <div class="turn-bubble" :style="{ '--agent-color': getColor() }">
    <div
      class="avatar"
      :style="{ backgroundColor: getColor() }"
      :aria-label="`${turn.display_name} のアバター`"
    >
      {{ turn.display_name.charAt(0) }}
    </div>
    <div class="content">
      <div class="header">
        <span class="name" :style="{ color: getColor() }">{{ turn.display_name }}</span>
        <span class="turn-number">Turn {{ turn.turn_number }}</span>
      </div>
      <p class="text">{{ turn.content }}</p>
    </div>
  </div>
</template>

<style scoped>
.turn-bubble {
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 0.75rem;
  border-left: 3px solid var(--agent-color);
  background: #f9fafb;
  transition: background 0.2s;
}

.turn-bubble:hover {
  background: #f3f4f6;
}

.avatar {
  flex-shrink: 0;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 0.875rem;
}

.content {
  flex: 1;
  min-width: 0;
}

.header {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.name {
  font-weight: 600;
  font-size: 0.875rem;
}

.turn-number {
  font-size: 0.75rem;
  color: #9ca3af;
}

.text {
  margin: 0;
  font-size: 0.9375rem;
  line-height: 1.6;
  color: #1f2937;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
