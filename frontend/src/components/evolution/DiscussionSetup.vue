<script setup lang="ts">
/**
 * DiscussionSetup.vue
 * Requirements: 22.1, 22.2 - マルチエージェント対話観覧シアター
 *
 * エージェント選択（2〜6人バリデーション）、テーマ入力、
 * 議論開始ボタンを提供するセットアップ UI コンポーネント。
 */

import { ref, computed } from 'vue'
import type { Agent } from './composables/useAgents'

const props = defineProps<{
  agents: Agent[]
}>()

const emit = defineEmits<{
  (e: 'start', agentIds: string[], theme: string): void
}>()

const selectedIds = ref<Set<string>>(new Set())
const theme = ref('')

const canStart = computed(() => {
  return selectedIds.value.size >= 2
    && selectedIds.value.size <= 6
    && theme.value.trim().length > 0
})

const validationMessage = computed(() => {
  if (selectedIds.value.size < 2) return 'エージェントを2人以上選択してください'
  if (selectedIds.value.size > 6) return 'エージェントは最大6人までです'
  if (!theme.value.trim()) return 'テーマを入力してください'
  return ''
})

function toggleAgent(agentId: string) {
  if (selectedIds.value.has(agentId)) {
    selectedIds.value.delete(agentId)
  } else {
    selectedIds.value.add(agentId)
  }
  // Set を再代入してリアクティビティを発火
  selectedIds.value = new Set(selectedIds.value)
}

function startDiscussion() {
  if (!canStart.value) return
  emit('start', Array.from(selectedIds.value), theme.value.trim())
}
</script>

<template>
  <div class="discussion-setup">
    <h3>議論設定</h3>

    <div class="agent-selection">
      <p>参加エージェント (2〜6人):</p>
      <div class="agent-chips">
        <button
          v-for="agent in agents"
          :key="agent.agent_id"
          type="button"
          :class="['chip', { active: selectedIds.has(agent.agent_id) }]"
          :aria-pressed="selectedIds.has(agent.agent_id)"
          @click="toggleAgent(agent.agent_id)"
        >
          {{ agent.display_name }}
        </button>
      </div>
      <p class="count">{{ selectedIds.size }} / 6 人選択中</p>
    </div>

    <div class="theme-input">
      <label for="discussion-theme">テーマ:</label>
      <input
        id="discussion-theme"
        v-model="theme"
        type="text"
        placeholder="議論テーマを入力..."
        maxlength="200"
      />
    </div>

    <p v-if="validationMessage" class="validation-msg">
      {{ validationMessage }}
    </p>

    <button
      class="start-btn"
      :disabled="!canStart"
      @click="startDiscussion"
    >
      議論を開始
    </button>
  </div>
</template>

<style scoped>
.discussion-setup { max-width: 600px; }
.agent-chips { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.5rem 0; }
.chip {
  padding: 0.5rem 1rem;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 2rem;
  background: var(--color-surface, rgba(24, 24, 27, 0.6));
  color: var(--color-foreground, #fafafa);
  cursor: pointer;
  transition: all 0.2s;
}
.chip:hover { border-color: rgba(109, 40, 217, 0.3); }
.chip.active { background: #6d28d9; color: white; border-color: #6d28d9; }
.count { font-size: 0.875rem; color: var(--color-muted, #a1a1aa); }
.theme-input { margin: 1rem 0; }
.theme-input input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 0.5rem;
  font-size: 1rem;
  background: var(--color-surface, #09090b);
  color: var(--color-foreground, #fafafa);
}
.theme-input input:focus {
  outline: none;
  border-color: #6d28d9;
  box-shadow: 0 0 0 2px rgba(109, 40, 217, 0.2);
}
.validation-msg { color: #ef4444; font-size: 0.875rem; }
.start-btn {
  padding: 0.75rem 1.5rem;
  background: linear-gradient(135deg, #6d28d9, #a78bfa);
  color: white;
  border: none;
  border-radius: 0.5rem;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.2s;
}
.start-btn:hover:not(:disabled) { box-shadow: 0 0 20px rgba(109, 40, 217, 0.3); }
.start-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
