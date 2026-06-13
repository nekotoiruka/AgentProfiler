<script setup lang="ts">
/**
 * EvolutionView — トモコレ風 Agent Evolution メインページ
 *
 * カジュアル & かわいいデザインで分身たちの世界を覗く体験を提供する。
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

// --- アバター絵文字（エージェントごとに割り当て） ---
const AVATARS = ['😊', '🤔', '😎', '🌟', '🎨', '🦊', '🐱', '🌈', '✨', '🍀']
function getAvatar(index: number): string {
  return AVATARS[index % AVATARS.length]
}

// --- Actions ---

async function handleLoadProfile() {
  loadStatus.value = null
  loadError.value = null

  if (!profileId.value.match(/^prof_\d{6}$/)) {
    loadError.value = 'prof_000001 のような形式で入力してね'
    return
  }

  try {
    await apiFetch<{ profile_id: string }>(`/v1/evolution/profiles/${profileId.value}/prompt`)
    loadStatus.value = '✨ プロファイル読み込み完了！'
    profileLoaded.value = true
    await listAgents(profileId.value)
  } catch (e: any) {
    if (e.status === 404) {
      loadError.value = 'このプロファイルはまだ登録されていないみたい。質問フローを完了してからもう一度試してね！'
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
    loadStatus.value = `🎉 「${agent.display_name}」が誕生したよ！`
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
  const params = new URLSearchParams(window.location.search)
  const pid = params.get('profile_id')
  if (pid) {
    profileId.value = pid
    handleLoadProfile()
  }
})
</script>

<template>
  <div class="evo">
    <!-- ヘッダー -->
    <header class="evo-header">
      <div class="evo-header__icon">🏠</div>
      <div>
        <h1 class="evo-header__title">わたしの分身たち</h1>
        <p class="evo-header__sub">みんなの様子を覗いてみよう</p>
      </div>
    </header>

    <!-- タブナビゲーション -->
    <nav class="evo-tabs">
      <button
        v-for="tab in ([
          { id: 'setup' as Tab, icon: '🏡', label: 'おへや' },
          { id: 'chat' as Tab, icon: '💬', label: 'おしゃべり' },
          { id: 'discussion' as Tab, icon: '🎪', label: 'みんなで会議' },
        ])"
        :key="tab.id"
        :class="['evo-tab', { 'evo-tab--active': activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <span class="evo-tab__icon">{{ tab.icon }}</span>
        <span class="evo-tab__label">{{ tab.label }}</span>
      </button>
    </nav>

    <!-- 設定タブ（おへや） -->
    <section v-if="activeTab === 'setup'" class="evo-panel">
      <div class="evo-card">
        <h2 class="evo-card__title">📋 プロファイル読み込み</h2>
        <div class="evo-input-group">
          <input
            v-model="profileId"
            type="text"
            placeholder="prof_000001"
            class="evo-input"
          />
          <button class="evo-btn evo-btn--primary" @click="handleLoadProfile">読み込む</button>
        </div>
        <p v-if="loadStatus" class="evo-msg evo-msg--ok">{{ loadStatus }}</p>
        <p v-if="loadError" class="evo-msg evo-msg--err">{{ loadError }}</p>
      </div>

      <div v-if="profileLoaded" class="evo-card">
        <h2 class="evo-card__title">🐣 新しい分身をつくる</h2>
        <div class="evo-input-group">
          <input
            v-model="newAgentName"
            type="text"
            placeholder="なまえを入力..."
            class="evo-input"
          />
          <button
            class="evo-btn evo-btn--accent"
            :disabled="!newAgentName.trim()"
            @click="handleCreateAgent"
          >
            うまれる！
          </button>
        </div>
      </div>

      <!-- 分身一覧 -->
      <div v-if="agents.length > 0" class="evo-card">
        <h2 class="evo-card__title">🏠 住んでいる分身たち</h2>
        <div class="evo-residents">
          <button
            v-for="(agent, idx) in agents"
            :key="agent.agent_id"
            class="evo-resident"
            @click="handleSelectAgent(agent)"
          >
            <span class="evo-resident__avatar">{{ getAvatar(idx) }}</span>
            <span class="evo-resident__name">{{ agent.display_name }}</span>
          </button>
        </div>
      </div>
    </section>

    <!-- チャットタブ（おしゃべり） -->
    <section v-if="activeTab === 'chat'" class="evo-panel evo-panel--chat">
      <aside class="evo-sidebar">
        <h3 class="evo-sidebar__title">だれと話す？</h3>
        <div class="evo-residents evo-residents--compact">
          <button
            v-for="(agent, idx) in agents"
            :key="agent.agent_id"
            :class="['evo-resident evo-resident--sm', { 'evo-resident--selected': selectedAgent?.agent_id === agent.agent_id }]"
            @click="handleSelectAgent(agent)"
          >
            <span class="evo-resident__avatar">{{ getAvatar(idx) }}</span>
            <span class="evo-resident__name">{{ agent.display_name }}</span>
          </button>
        </div>
        <p v-if="agents.length === 0" class="evo-hint">
          おへやタブで分身を作ってね
        </p>
      </aside>
      <main class="evo-chat-main">
        <template v-if="selectedAgent">
          <div class="evo-chat-header">
            <span class="evo-chat-header__avatar">{{ getAvatar(agents.findIndex(a => a.agent_id === selectedAgent!.agent_id)) }}</span>
            <span class="evo-chat-header__name">{{ selectedAgent.display_name }}</span>
            <span class="evo-chat-header__status">おしゃべり中</span>
          </div>
          <ChatThread :messages="messages" :streaming="streaming" />
          <ChatInput :disabled="chatLoading || streaming" @send="handleSendMessage" />
        </template>
        <div v-else class="evo-empty">
          <p>← だれかをえらんでね</p>
        </div>
      </main>
    </section>

    <!-- ディスカッションタブ（みんなで会議） -->
    <section v-if="activeTab === 'discussion'" class="evo-panel">
      <template v-if="!discussionId && !discStreaming">
        <div class="evo-card">
          <h2 class="evo-card__title">🎪 みんなで会議をひらく</h2>
          <DiscussionSetup :agents="agents" @start="handleStartDiscussion" />
          <p v-if="agents.length < 2" class="evo-hint">
            会議には2人以上の分身が必要だよ。おへやで仲間を増やしてね！
          </p>
        </div>
      </template>
      <template v-else>
        <div class="evo-card evo-card--theater">
          <DiscussionTheater
            :turns="turns"
            :streaming="discStreaming"
            :progress="progress"
            :total-expected-turns="totalExpectedTurns"
          />
        </div>
        <button
          v-if="!discStreaming"
          class="evo-btn evo-btn--secondary"
          @click="resetDiscussion"
        >
          🔄 もういっかい！
        </button>
      </template>
    </section>
  </div>
</template>

<style scoped>
/* === トモコレ風テーマ: パステル＆まるっとしたUI === */

.evo {
  max-width: 1000px;
  margin: 0 auto;
  padding: 1rem;
  font-family: 'Hiragino Maru Gothic ProN', 'Kosugi Maru', system-ui, sans-serif;
  background: linear-gradient(180deg, #fef9ff 0%, #f0f7ff 50%, #f5fff0 100%);
  min-height: 100vh;
}

/* --- ヘッダー --- */
.evo-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem 0;
  margin-bottom: 0.5rem;
}
.evo-header__icon { font-size: 2rem; }
.evo-header__title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #5b4a8a;
  margin: 0;
}
.evo-header__sub {
  font-size: 0.8rem;
  color: #9b8ec4;
  margin: 0;
}

/* --- タブ --- */
.evo-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.evo-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem 0.5rem;
  border: 2px solid #e8dff5;
  border-radius: 16px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}
.evo-tab:hover { background: #faf5ff; border-color: #d4c4ed; }
.evo-tab--active {
  background: linear-gradient(135deg, #e8dff5, #d4eaff);
  border-color: #b4a0d9;
  box-shadow: 0 2px 8px rgba(139, 115, 200, 0.15);
}
.evo-tab__icon { font-size: 1.5rem; }
.evo-tab__label { font-size: 0.75rem; font-weight: 600; color: #5b4a8a; }

/* --- パネル --- */
.evo-panel { min-height: 400px; }
.evo-panel--chat { display: flex; gap: 0.75rem; height: 550px; }

/* --- カード --- */
.evo-card {
  background: white;
  border: 2px solid #ede7f6;
  border-radius: 20px;
  padding: 1.25rem;
  margin-bottom: 1rem;
  box-shadow: 0 2px 12px rgba(139, 115, 200, 0.06);
}
.evo-card--theater { padding: 0.75rem; }
.evo-card__title {
  font-size: 1rem;
  font-weight: 700;
  color: #5b4a8a;
  margin: 0 0 0.75rem;
}

/* --- インプット --- */
.evo-input-group { display: flex; gap: 0.5rem; }
.evo-input {
  flex: 1;
  padding: 0.6rem 1rem;
  border: 2px solid #e8dff5;
  border-radius: 12px;
  font-size: 0.9rem;
  background: #faf8ff;
  transition: border-color 0.2s;
}
.evo-input:focus { border-color: #b4a0d9; outline: none; background: white; }

/* --- ボタン --- */
.evo-btn {
  padding: 0.6rem 1.25rem;
  border: none;
  border-radius: 12px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.evo-btn--primary { background: #7c5cbf; color: white; }
.evo-btn--primary:hover { background: #6a4bad; }
.evo-btn--accent { background: #ff8fab; color: white; }
.evo-btn--accent:hover { background: #f57c9e; }
.evo-btn--accent:disabled { background: #f0c4d4; cursor: not-allowed; }
.evo-btn--secondary {
  background: white;
  border: 2px solid #e8dff5;
  color: #5b4a8a;
  margin-top: 0.75rem;
}
.evo-btn--secondary:hover { background: #faf5ff; }

/* --- メッセージ --- */
.evo-msg { font-size: 0.8rem; margin-top: 0.5rem; border-radius: 8px; padding: 0.4rem 0.75rem; }
.evo-msg--ok { background: #e8f8e8; color: #2d7a3a; }
.evo-msg--err { background: #fff0f0; color: #c53030; }
.evo-hint { font-size: 0.8rem; color: #9b8ec4; font-style: italic; margin-top: 0.5rem; }

/* --- 分身カード（レジデンツ） --- */
.evo-residents {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 0.75rem;
}
.evo-residents--compact {
  grid-template-columns: 1fr;
  gap: 0.5rem;
}
.evo-resident {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.375rem;
  padding: 1rem 0.5rem;
  background: linear-gradient(135deg, #fef5ff, #f5f0ff);
  border: 2px solid #ede7f6;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
}
.evo-resident:hover {
  border-color: #b4a0d9;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(139, 115, 200, 0.15);
}
.evo-resident--sm {
  flex-direction: row;
  padding: 0.5rem 0.75rem;
  border-radius: 12px;
}
.evo-resident--selected {
  background: linear-gradient(135deg, #e4d4f7, #d4e8ff);
  border-color: #8b73c8;
}
.evo-resident__avatar { font-size: 1.75rem; }
.evo-resident--sm .evo-resident__avatar { font-size: 1.25rem; }
.evo-resident__name { font-size: 0.8rem; font-weight: 600; color: #5b4a8a; }

/* --- サイドバー --- */
.evo-sidebar {
  width: 180px;
  flex-shrink: 0;
  padding-right: 0.5rem;
  border-right: 2px solid #ede7f6;
  overflow-y: auto;
}
.evo-sidebar__title {
  font-size: 0.8rem;
  font-weight: 700;
  color: #9b8ec4;
  margin: 0 0 0.5rem;
}

/* --- チャットメイン --- */
.evo-chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: white;
  border: 2px solid #ede7f6;
  border-radius: 20px;
  overflow: hidden;
}
.evo-chat-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, #f8f0ff, #f0f5ff);
  border-bottom: 2px solid #ede7f6;
}
.evo-chat-header__avatar { font-size: 1.5rem; }
.evo-chat-header__name { font-weight: 700; color: #5b4a8a; font-size: 0.9rem; }
.evo-chat-header__status { font-size: 0.7rem; color: #4ade80; margin-left: auto; }

/* --- 空状態 --- */
.evo-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: #b4a0d9;
  font-size: 1rem;
}
</style>
