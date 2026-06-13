<script setup lang="ts">
/**
 * EvolutionView — Agent Evolution メインページ
 *
 * モダン & クリーンなデザイン。
 * ページ表示時に全エージェントを自動取得し、即座に操作可能。
 */

import { ref, onMounted, computed } from 'vue'
import ChatThread from '@/components/evolution/ChatThread.vue'
import ChatInput from '@/components/evolution/ChatInput.vue'
import DiscussionSetup from '@/components/evolution/DiscussionSetup.vue'
import DiscussionTheater from '@/components/evolution/DiscussionTheater.vue'
import { useAgents, type Agent } from '@/components/evolution/composables/useAgents'
import { useChat } from '@/components/evolution/composables/useChat'
import { useDiscussion } from '@/components/evolution/composables/useDiscussion'
import { apiFetch } from '@/composables/useApi'

type Tab = 'agents' | 'chat' | 'discussion'

const activeTab = ref<Tab>('agents')

// --- Agents ---
const { agents, loading: agentsLoading, listAgents, createAgent, deleteAgent } = useAgents()
const newAgentName = ref('')
const createError = ref<string | null>(null)

// --- Profiles ---
const profiles = ref<{ profile_id: string }[]>([])
const selectedProfileId = ref<string | null>(null)

async function loadProfiles() {
  try {
    profiles.value = await apiFetch<{ profile_id: string }[]>('/v1/evolution/profiles')
    if (profiles.value.length === 1) {
      selectedProfileId.value = profiles.value[0].profile_id
    }
  } catch {
    // Evolution 未初期化時は空
  }
}

// --- Chat ---
const selectedAgent = ref<Agent | null>(null)
const {
  messages, threadId, loading: chatLoading, streaming,
  sendMessage, switchThread,
} = useChat()

// --- Discussion ---
const {
  turns, discussionId, streaming: discStreaming,
  progress, totalExpectedTurns, startDiscussion, reset: resetDiscussion,
} = useDiscussion()

// --- Computed ---
const hasAgents = computed(() => agents.value.length > 0)

// --- Actions ---
async function handleCreateAgent() {
  createError.value = null
  const name = newAgentName.value.trim()
  if (!name || !selectedProfileId.value) return
  const agent = await createAgent(selectedProfileId.value, name)
  if (agent) {
    newAgentName.value = ''
  } else {
    createError.value = '作成に失敗しました。プロファイルが正しく登録されているか確認してください。'
  }
}

function selectAgent(agent: Agent) {
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
  activeTab.value = 'discussion'
}

onMounted(async () => {
  // 全エージェントを自動取得（プロファイル指定不要）
  await listAgents()
  // 登録済みプロファイル一覧を取得
  await loadProfiles()

  // URL パラメータで profile_id が指定されていれば自動選択
  const params = new URLSearchParams(window.location.search)
  const pid = params.get('profile_id')
  if (pid) selectedProfileId.value = pid
})
</script>

<template>
  <div class="ev">
    <!-- ヘッダー -->
    <header class="ev-header">
      <h1 class="ev-header__title">Agent Evolution</h1>
      <p class="ev-header__desc">あなたの分身たちと対話する</p>
    </header>

    <!-- ナビゲーション -->
    <nav class="ev-nav">
      <button
        v-for="tab in ([
          { id: 'agents' as Tab, label: 'エージェント' },
          { id: 'chat' as Tab, label: 'チャット' },
          { id: 'discussion' as Tab, label: 'ディスカッション' },
        ])"
        :key="tab.id"
        :class="['ev-nav__item', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- エージェント一覧タブ -->
    <section v-if="activeTab === 'agents'" class="ev-section">
      <!-- 新規作成 -->
      <div class="ev-create">
        <h2 class="ev-section__title">新しいエージェントを作成</h2>
        <div v-if="profiles.length === 0" class="ev-hint">
          プロファイルが登録されていません。
          <router-link to="/survey" class="ev-link">質問フローを完了</router-link>してください。
        </div>
        <div v-else class="ev-create__form">
          <select v-model="selectedProfileId" class="ev-select">
            <option :value="null" disabled>プロファイルを選択</option>
            <option v-for="p in profiles" :key="p.profile_id" :value="p.profile_id">
              {{ p.profile_id }}
            </option>
          </select>
          <input
            v-model="newAgentName"
            class="ev-input"
            placeholder="エージェント名"
            @keydown.enter="handleCreateAgent"
          />
          <button
            class="ev-btn ev-btn--primary"
            :disabled="!newAgentName.trim() || !selectedProfileId"
            @click="handleCreateAgent"
          >
            作成
          </button>
        </div>
        <p v-if="createError" class="ev-error">{{ createError }}</p>
      </div>

      <!-- エージェントリスト -->
      <div v-if="agentsLoading" class="ev-loading">読み込み中...</div>
      <div v-else-if="!hasAgents" class="ev-empty-state">
        <div class="ev-empty-state__icon">🤖</div>
        <p class="ev-empty-state__text">まだエージェントがいません</p>
        <p class="ev-empty-state__sub">質問フローを完了してプロファイルを作成し、分身エージェントを生成しましょう</p>
        <div class="ev-empty-state__actions">
          <router-link to="/survey" class="ev-btn ev-btn--primary">
            質問フローを始める
          </router-link>
        </div>
      </div>
      <div v-else class="ev-agent-grid">
        <div
          v-for="agent in agents"
          :key="agent.agent_id"
          class="ev-agent-card"
          @click="selectAgent(agent)"
        >
          <div class="ev-agent-card__avatar">
            {{ agent.display_name.charAt(0) }}
          </div>
          <div class="ev-agent-card__info">
            <span class="ev-agent-card__name">{{ agent.display_name }}</span>
            <span class="ev-agent-card__meta">{{ agent.profile_id }}</span>
          </div>
          <button
            class="ev-agent-card__action"
            title="チャットを開始"
          >
            →
          </button>
        </div>
      </div>
    </section>

    <!-- チャットタブ -->
    <section v-if="activeTab === 'chat'" class="ev-section ev-section--chat">
      <!-- サイドバー -->
      <aside class="ev-chat-sidebar">
        <div
          v-for="agent in agents"
          :key="agent.agent_id"
          :class="['ev-chat-sidebar__item', { active: selectedAgent?.agent_id === agent.agent_id }]"
          @click="selectAgent(agent)"
        >
          <div class="ev-chat-sidebar__avatar">{{ agent.display_name.charAt(0) }}</div>
          <span class="ev-chat-sidebar__name">{{ agent.display_name }}</span>
        </div>
        <p v-if="!hasAgents" class="ev-chat-sidebar__empty">エージェントを作成してください</p>
      </aside>

      <!-- チャットエリア -->
      <main class="ev-chat-area">
        <template v-if="selectedAgent">
          <div class="ev-chat-area__header">
            <div class="ev-chat-area__avatar">{{ selectedAgent.display_name.charAt(0) }}</div>
            <div>
              <div class="ev-chat-area__name">{{ selectedAgent.display_name }}</div>
              <div class="ev-chat-area__status">オンライン</div>
            </div>
          </div>
          <div class="ev-chat-area__messages">
            <ChatThread :messages="messages" :streaming="streaming" />
          </div>
          <ChatInput :disabled="chatLoading || streaming" @send="handleSendMessage" />
        </template>
        <div v-else class="ev-chat-area__placeholder">
          <p>左のリストからエージェントを選択してください</p>
        </div>
      </main>
    </section>

    <!-- ディスカッションタブ -->
    <section v-if="activeTab === 'discussion'" class="ev-section">
      <template v-if="!discussionId && !discStreaming">
        <h2 class="ev-section__title">マルチエージェント・ディスカッション</h2>
        <p class="ev-section__desc">複数のエージェントにテーマを与えて、議論を観察しましょう。</p>
        <DiscussionSetup :agents="agents" @start="handleStartDiscussion" />
        <p v-if="agents.length < 2" class="ev-hint">
          ディスカッションには2体以上のエージェントが必要です。
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
          class="ev-btn ev-btn--secondary ev-btn--mt"
          @click="resetDiscussion"
        >
          新しいディスカッションを開始
        </button>
      </template>
    </section>
  </div>
</template>

<style scoped>
/* ============================================================
   Agent Evolution — プロダクションレベル UI
   カラー: ニュートラル基調 + ラベンダーアクセント
   ============================================================ */

.ev {
  max-width: 1080px;
  margin: 0 auto;
  padding: 1.5rem 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  color: #1a1a2e;
}

/* --- Header --- */
.ev-header { margin-bottom: 2rem; }
.ev-header__title {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0;
}
.ev-header__desc {
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
  color: #64748b;
}

/* --- Nav --- */
.ev-nav {
  display: flex;
  gap: 0.25rem;
  padding: 4px;
  background: #f1f5f9;
  border-radius: 10px;
  margin-bottom: 2rem;
}
.ev-nav__item {
  flex: 1;
  padding: 0.6rem 1rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 0.875rem;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
}
.ev-nav__item:hover { color: #1a1a2e; }
.ev-nav__item.active {
  background: white;
  color: #1a1a2e;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* --- Section --- */
.ev-section { min-height: 400px; }
.ev-section--chat { display: flex; gap: 1px; height: 600px; background: #e2e8f0; border-radius: 12px; overflow: hidden; }
.ev-section__title { font-size: 1.125rem; font-weight: 600; margin: 0 0 0.5rem; }
.ev-section__desc { font-size: 0.875rem; color: #64748b; margin: 0 0 1.5rem; }

/* --- Create form --- */
.ev-create { margin-bottom: 2rem; }
.ev-create__form { display: flex; gap: 0.5rem; margin-top: 0.75rem; }
.ev-input {
  padding: 0.6rem 0.875rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.875rem;
  background: white;
  transition: border-color 0.15s;
  flex: 1;
}
.ev-input--sm { max-width: 180px; }
.ev-input:focus { border-color: #7c5cbf; outline: none; }
.ev-select {
  padding: 0.6rem 0.875rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.875rem;
  background: white;
  min-width: 160px;
}
.ev-link { color: #6d28d9; text-decoration: underline; }
.ev-error { font-size: 0.8rem; color: #dc2626; margin-top: 0.5rem; }

/* --- Button --- */
.ev-btn {
  padding: 0.6rem 1.25rem;
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.ev-btn--primary { background: #6d28d9; color: white; }
.ev-btn--primary:hover { background: #5b21b6; }
.ev-btn--primary:disabled { background: #c4b5fd; cursor: not-allowed; }
.ev-btn--secondary { background: white; border: 1px solid #e2e8f0; color: #374151; }
.ev-btn--secondary:hover { background: #f8fafc; }
.ev-btn--mt { margin-top: 1rem; }

/* --- Agent Grid --- */
.ev-agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}
.ev-agent-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.ev-agent-card:hover {
  border-color: #c4b5fd;
  box-shadow: 0 2px 8px rgba(109, 40, 217, 0.06);
}
.ev-agent-card__avatar {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #ede9fe, #ddd6fe);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1rem;
  color: #6d28d9;
  flex-shrink: 0;
}
.ev-agent-card__info { flex: 1; min-width: 0; }
.ev-agent-card__name {
  display: block;
  font-weight: 600;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ev-agent-card__meta {
  display: block;
  font-size: 0.75rem;
  color: #94a3b8;
  margin-top: 0.125rem;
}
.ev-agent-card__action {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.15s;
}
.ev-agent-card__action:hover { background: #ede9fe; color: #6d28d9; }

/* --- Empty / Loading --- */
.ev-loading { padding: 2rem; text-align: center; color: #94a3b8; }
.ev-empty-state { padding: 4rem 2rem; text-align: center; }
.ev-empty-state__icon { font-size: 3rem; margin-bottom: 1rem; }
.ev-empty-state__text { font-size: 1.125rem; font-weight: 600; color: #374151; margin: 0; }
.ev-empty-state__sub { font-size: 0.875rem; color: #94a3b8; margin: 0.5rem 0 0; max-width: 400px; margin-left: auto; margin-right: auto; line-height: 1.5; }
.ev-empty-state__actions { margin-top: 1.5rem; }
.ev-empty-state__actions .ev-btn { display: inline-block; text-decoration: none; }
.ev-hint { font-size: 0.8rem; color: #94a3b8; margin-top: 0.75rem; }

/* --- Chat sidebar --- */
.ev-chat-sidebar {
  width: 220px;
  background: white;
  padding: 1rem;
  overflow-y: auto;
}
.ev-chat-sidebar__item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.625rem;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 0.25rem;
  transition: background 0.15s;
}
.ev-chat-sidebar__item:hover { background: #f8fafc; }
.ev-chat-sidebar__item.active { background: #ede9fe; }
.ev-chat-sidebar__avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #ede9fe, #ddd6fe);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.8rem;
  color: #6d28d9;
  flex-shrink: 0;
}
.ev-chat-sidebar__name { font-size: 0.8rem; font-weight: 500; }
.ev-chat-sidebar__empty { font-size: 0.75rem; color: #94a3b8; padding: 1rem 0; }

/* --- Chat area --- */
.ev-chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fafbfc;
  min-width: 0;
}
.ev-chat-area__header {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.875rem 1.25rem;
  background: white;
  border-bottom: 1px solid #e2e8f0;
}
.ev-chat-area__avatar {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: linear-gradient(135deg, #ede9fe, #ddd6fe);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.9rem;
  color: #6d28d9;
}
.ev-chat-area__name { font-weight: 600; font-size: 0.9rem; }
.ev-chat-area__status { font-size: 0.7rem; color: #10b981; }
.ev-chat-area__messages { flex: 1; overflow-y: auto; }
.ev-chat-area__placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 0.875rem;
}
</style>
