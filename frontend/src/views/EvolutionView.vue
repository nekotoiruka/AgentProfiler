<script setup lang="ts">
/**
 * EvolutionView — Agent Evolution メインページ
 *
 * 3つのタブで構成:
 * 1. チャット: 分身セレクト + 1対1チャット
 * 2. ディスカッション: マルチエージェント議論シアター
 * 3. 設定: プロファイルロード + エージェント作成
 */

import { ref, onMounted } from 'vue'
import AgentList from '@/components/evolution/AgentList.vue'
import ChatThread from '@/components/evolution/ChatThread.vue'
import ChatInput from '@/components/evolution/ChatInput.vue'
import DiscussionSetup from '@/components/evolution/DiscussionSetup.vue'
import DiscussionTheater from '@/components/evolution/DiscussionTheater.vue'
import { useAgents, type Agent } from '@/components/evolution/composables/useAgents'
import { useChat } from '@/components/evolution/composables/useChat'
import { useDiscussion } from '@/components/evolution/composables/useDiscussion'
import { apiFetch } from '@/composables/useApi'

type Tab = 'chat' | 'discussion' | 'setup'

const activeTab = ref<Tab>('setup')

// --- Setup tab ---
const profileId = ref('')
const loadStatus = ref<string | null>(null)
const loadError = ref<string | null>(null)
const newAgentName = ref('')
const profileLoaded = ref(false)

// --- Chat tab ---
const { agents, loading: agentsLoading, listAgents, createAgent } = useAgents()
const selectedAgent = ref<Agent | null>(null)
const {
  messages, threadId, loading: chatLoading, streaming,
  sendMessage, switchThread,
} = useChat()

// --- Discussion tab ---
const {
  turns, discussionId, streaming: discStreaming,
  progress, totalExpectedTurns, startDiscussion, reset: resetDiscussion,
} = useDiscussion()

// --- Actions ---

async function handleLoadProfile() {
  loadStatus.value = null
  loadError.value = null

  if (!profileId.value.match(/^prof_\d{6}$/)) {
    loadError.value = 'profile_id は prof_000001 の形式で入力してください'
    return
  }

  try {
    // まず既存セッションからプロファイルをロードする API を呼ぶ
    const resp = await apiFetch<{ profile_id: string; status: string }>(
      `/v1/evolution/profiles/${profileId.value}/prompt`
    )
    // プロンプト取得成功 = 既にロード済み
    loadStatus.value = `プロファイル ${resp.profile_id} は既にロード済みです`
    profileLoaded.value = true
    await listAgents(profileId.value)
  } catch (e: any) {
    if (e.status === 404) {
      loadError.value = 'このプロファイルはまだシステムにロードされていません。Swagger UI (http://localhost:8001/docs) から POST /profiles でロードしてください。'
    } else {
      loadError.value = e.message
    }
  }
}

async function handleCreateAgent() {
  if (!newAgentName.value.trim() || !profileId.value) return
  const agent = await createAgent(profileId.value, newAgentName.value.trim())
  if (agent) {
    newAgentName.value = ''
    loadStatus.value = `エージェント「${agent.display_name}」を作成しました`
  }
}

function handleSelectAgent(agent: Agent) {
  selectedAgent.value = agent
  switchThread(null)
  activeTab.value = 'chat'
}

async function handleSendMessage(message: string) {
  if (!selectedAgent.value) return
  await sendMessage(selectedAgent.value.agent_id, message)
}

function handleStartDiscussion(agentIds: string[], theme: string) {
  resetDiscussion()
  startDiscussion(agentIds, theme, 5)
}

onMounted(() => {
  // profile_id がクエリパラメータにあれば自動設定
  const params = new URLSearchParams(window.location.search)
  const pid = params.get('profile_id')
  if (pid) {
    profileId.value = pid
    handleLoadProfile()
  }
})
</script>

<template>
  <div class="evolution-view">
    <header class="evolution-header">
      <h1>Agent Evolution</h1>
      <p class="subtitle">分身エージェントの対話・管理</p>
    </header>

    <!-- タブ切り替え -->
    <nav class="tabs" role="tablist">
      <button
        v-for="tab in (['setup', 'chat', 'discussion'] as Tab[])"
        :key="tab"
        role="tab"
        :aria-selected="activeTab === tab"
        :class="['tab', { active: activeTab === tab }]"
        @click="activeTab = tab"
      >
        {{ tab === 'setup' ? '⚙️ 設定' : tab === 'chat' ? '💬 チャット' : '🎭 ディスカッション' }}
      </button>
    </nav>

    <!-- 設定タブ -->
    <section v-if="activeTab === 'setup'" class="tab-content">
      <div class="setup-section">
        <h2>プロファイルロード</h2>
        <div class="input-row">
          <input
            v-model="profileId"
            type="text"
            placeholder="prof_000001"
            class="text-input"
          />
          <button class="btn-primary" @click="handleLoadProfile">確認</button>
        </div>
        <p v-if="loadStatus" class="status-msg success">{{ loadStatus }}</p>
        <p v-if="loadError" class="status-msg error">{{ loadError }}</p>
      </div>

      <div v-if="profileLoaded" class="setup-section">
        <h2>エージェント作成</h2>
        <div class="input-row">
          <input
            v-model="newAgentName"
            type="text"
            placeholder="表示名を入力..."
            class="text-input"
          />
          <button
            class="btn-primary"
            :disabled="!newAgentName.trim()"
            @click="handleCreateAgent"
          >
            作成
          </button>
        </div>
      </div>

      <div v-if="agents.length > 0" class="setup-section">
        <h2>登録済みエージェント</h2>
        <AgentList :profile-id="profileId" @select="handleSelectAgent" />
      </div>
    </section>

    <!-- チャットタブ -->
    <section v-if="activeTab === 'chat'" class="tab-content chat-layout">
      <aside class="chat-sidebar">
        <AgentList
          v-if="profileId"
          :profile-id="profileId"
          @select="handleSelectAgent"
        />
        <p v-else class="hint">設定タブでプロファイルをロードしてください</p>
      </aside>
      <main class="chat-main">
        <template v-if="selectedAgent">
          <div class="chat-header">
            <span class="agent-name">{{ selectedAgent.display_name }}</span>
            <span v-if="threadId" class="thread-id">Thread: {{ threadId.slice(0, 8) }}...</span>
          </div>
          <ChatThread :messages="messages" :streaming="streaming" />
          <ChatInput :disabled="chatLoading || streaming" @send="handleSendMessage" />
        </template>
        <div v-else class="empty-state">
          <p>左のリストからエージェントを選択してください</p>
        </div>
      </main>
    </section>

    <!-- ディスカッションタブ -->
    <section v-if="activeTab === 'discussion'" class="tab-content">
      <template v-if="!discussionId && !discStreaming">
        <DiscussionSetup :agents="agents" @start="handleStartDiscussion" />
        <p v-if="agents.length < 2" class="hint">
          ディスカッションには2体以上のエージェントが必要です。設定タブでエージェントを作成してください。
        </p>
      </template>
      <template v-else>
        <DiscussionTheater
          :turns="turns"
          :streaming="discStreaming"
          :progress="progress"
          :total-expected-turns="totalExpectedTurns"
        />
        <button
          v-if="!discStreaming"
          class="btn-secondary"
          @click="resetDiscussion"
        >
          新しいディスカッションを開始
        </button>
      </template>
    </section>
  </div>
</template>

<style scoped>
.evolution-view {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.5rem 1rem;
}

.evolution-header {
  text-align: center;
  margin-bottom: 1.5rem;
}
.evolution-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  color: #1f2937;
  margin: 0;
}
.subtitle {
  color: #6b7280;
  font-size: 0.875rem;
  margin: 0.25rem 0 0;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid #e5e7eb;
  margin-bottom: 1.5rem;
}
.tab {
  padding: 0.75rem 1.5rem;
  border: none;
  background: none;
  font-size: 0.9375rem;
  font-weight: 500;
  color: #6b7280;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}
.tab.active {
  color: #4f46e5;
  border-bottom-color: #4f46e5;
}
.tab:hover:not(.active) { color: #374151; }

/* Tab content */
.tab-content { min-height: 400px; }

/* Setup */
.setup-section { margin-bottom: 2rem; }
.setup-section h2 { font-size: 1.125rem; font-weight: 600; margin-bottom: 0.75rem; }
.input-row { display: flex; gap: 0.5rem; }
.text-input {
  flex: 1;
  padding: 0.625rem 0.875rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.9375rem;
}
.btn-primary {
  padding: 0.625rem 1.25rem;
  background: #4f46e5;
  color: white;
  border: none;
  border-radius: 0.5rem;
  font-weight: 500;
  cursor: pointer;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  background: white;
  cursor: pointer;
}
.status-msg { font-size: 0.875rem; margin-top: 0.5rem; }
.status-msg.success { color: #059669; }
.status-msg.error { color: #dc2626; }
.hint { color: #9ca3af; font-size: 0.875rem; font-style: italic; }

/* Chat layout */
.chat-layout { display: flex; gap: 1rem; height: 600px; }
.chat-sidebar { width: 220px; flex-shrink: 0; overflow-y: auto; border-right: 1px solid #e5e7eb; padding-right: 1rem; }
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.5rem 0; border-bottom: 1px solid #e5e7eb; margin-bottom: 0.5rem;
}
.agent-name { font-weight: 600; font-size: 1rem; }
.thread-id { font-size: 0.75rem; color: #9ca3af; }
.empty-state { display: flex; align-items: center; justify-content: center; flex: 1; color: #9ca3af; }
</style>
