<script setup lang="ts">
/**
 * AgentList コンポーネント
 * アクティブエージェント一覧を表示し、選択イベントを emit する。
 * Validates: Requirements 21.1, 21.2
 */

import { ref, onMounted } from 'vue'
import { useAgents, type Agent } from './composables/useAgents'

const props = defineProps<{
  profileId: string
}>()

const emit = defineEmits<{
  (e: 'select', agent: Agent): void
}>()

const { agents, loading, listAgents } = useAgents()
const selectedAgentId = ref<string | null>(null)

onMounted(() => {
  listAgents(props.profileId)
})

function selectAgent(agent: Agent) {
  selectedAgentId.value = agent.agent_id
  emit('select', agent)
}

/** キーボード操作でもエージェント選択を可能にする */
function handleKeydown(event: KeyboardEvent, agent: Agent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    selectAgent(agent)
  }
}
</script>

<template>
  <div class="agent-list">
    <h3 class="agent-list-title">分身一覧</h3>
    <div v-if="loading" class="loading">読み込み中...</div>
    <ul v-else role="listbox" aria-label="エージェント一覧">
      <li
        v-for="agent in agents"
        :key="agent.agent_id"
        :class="{ selected: agent.agent_id === selectedAgentId }"
        role="option"
        tabindex="0"
        :aria-selected="agent.agent_id === selectedAgentId"
        @click="selectAgent(agent)"
        @keydown="handleKeydown($event, agent)"
      >
        {{ agent.display_name }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.agent-list-title {
  margin: 0 0 0.75rem;
  font-size: 1rem;
  font-weight: 600;
  color: #1f2937;
}

.agent-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.agent-list li {
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background-color 0.2s;
  outline: none;
}

.agent-list li:hover {
  background-color: #f3f4f6;
}

.agent-list li:focus-visible {
  box-shadow: 0 0 0 2px #3b82f6;
}

.agent-list li.selected {
  background-color: #e0e7ff;
  font-weight: 600;
}

.loading {
  padding: 0.75rem 1rem;
  color: #6b7280;
  font-size: 0.875rem;
}
</style>
