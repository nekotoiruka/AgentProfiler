<script setup lang="ts">
/**
 * DiscussionTheater.vue
 * Requirements: 22.3, 22.4, 22.5, 22.6 - マルチエージェント対話観覧シアター
 *
 * マルチエージェント議論の視覚的観覧ビュー。
 * - ターンバブルのストリーミング表示（SSE リアルタイム対応）
 * - Playback モード切替: real-time / simulation speed
 * - ターンカウンター + プログレスバー
 * - 自動スクロール
 */

import { ref, computed, watch, nextTick } from 'vue'
import TurnBubble from './TurnBubble.vue'
import type { DiscussionTurn } from './composables/useDiscussion'

export type PlaybackMode = 'realtime' | 'simulation'

const props = defineProps<{
  turns: DiscussionTurn[]
  streaming: boolean
  progress: number
  totalExpectedTurns: number
}>()

const theaterContainer = ref<HTMLElement | null>(null)
const playbackMode = ref<PlaybackMode>('realtime')

// エージェント → カラーインデックスのマッピングを構築
const agentColorMap = computed(() => {
  const map = new Map<string, number>()
  let index = 0
  for (const turn of props.turns) {
    if (!map.has(turn.agent_id)) {
      map.set(turn.agent_id, index++)
    }
  }
  return map
})

// 新しいターン追加時に自動スクロール
watch(() => props.turns.length, async () => {
  await nextTick()
  if (theaterContainer.value) {
    theaterContainer.value.scrollTop = theaterContainer.value.scrollHeight
  }
})

function togglePlaybackMode() {
  playbackMode.value = playbackMode.value === 'realtime' ? 'simulation' : 'realtime'
}
</script>

<template>
  <div class="discussion-theater">
    <div class="theater-header">
      <div class="progress-info">
        <span class="turn-counter">
          {{ turns.length }} / {{ totalExpectedTurns }} ターン
        </span>
        <div
          class="progress-bar"
          role="progressbar"
          :aria-valuenow="progress"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="`議論進行度 ${progress}%`"
        >
          <div class="progress-fill" :style="{ width: progress + '%' }"></div>
        </div>
      </div>

      <div class="controls">
        <button
          class="mode-toggle"
          :class="{ active: playbackMode === 'simulation' }"
          @click="togglePlaybackMode"
          :aria-pressed="playbackMode === 'simulation'"
        >
          {{ playbackMode === 'realtime' ? '⚡ リアルタイム' : '🎬 シミュレーション' }}
        </button>
        <span v-if="streaming" class="live-badge">● LIVE</span>
      </div>
    </div>

    <div ref="theaterContainer" class="turns-container">
      <TurnBubble
        v-for="turn in turns"
        :key="`${turn.discussion_id}-${turn.turn_number}`"
        :turn="turn"
        :color-index="agentColorMap.get(turn.agent_id) ?? 0"
      />

      <p v-if="!turns.length && !streaming" class="empty-state">
        議論を開始するとターンがここに表示されます
      </p>
    </div>
  </div>
</template>

<style scoped>
.discussion-theater {
  display: flex;
  flex-direction: column;
  height: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  overflow: hidden;
  background: white;
}

.theater-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e5e7eb;
  background: #fafafa;
}

.progress-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
}

.turn-counter {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  white-space: nowrap;
}

.progress-bar {
  flex: 1;
  max-width: 200px;
  height: 6px;
  background: #e5e7eb;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #4f46e5;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.mode-toggle {
  padding: 0.375rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 1rem;
  background: white;
  font-size: 0.8125rem;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-toggle.active {
  background: #4f46e5;
  color: white;
  border-color: #4f46e5;
}

.live-badge {
  font-size: 0.75rem;
  font-weight: 600;
  color: #ef4444;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.turns-container {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.empty-state {
  text-align: center;
  color: #9ca3af;
  font-size: 0.875rem;
  margin-top: 2rem;
}
</style>
