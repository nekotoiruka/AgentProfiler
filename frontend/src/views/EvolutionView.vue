<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import ChatThread from '@/components/evolution/ChatThread.vue'
import ChatInput from '@/components/evolution/ChatInput.vue'
import DiscussionSetup from '@/components/evolution/DiscussionSetup.vue'
import DiscussionTheater from '@/components/evolution/DiscussionTheater.vue'
import { useAgents, type Agent } from '@/components/evolution/composables/useAgents'
import { useChat } from '@/components/evolution/composables/useChat'
import { useDiscussion } from '@/components/evolution/composables/useDiscussion'
import { apiFetch } from '@/composables/useApi'

type Tab = 'agents' | 'chat' | 'discussion' | 'registry'
const activeTab = ref<Tab>('agents')

const { agents, registry, loading: agentsLoading, listAgents, listRegistry, createAgent, publishAgent, unpublishAgent } = useAgents()
const profiles = ref<{ profile_id: string }[]>([])
const selectedProfileId = ref<string | null>(null)
const newAgentName = ref('')
const createError = ref<string | null>(null)
const showPublishDialog = ref(false)
const publishTargetAgent = ref<Agent | null>(null)

const selectedAgent = ref<Agent | null>(null)
const { messages, streaming, loading: chatLoading, sendMessage, switchThread } = useChat()
const { turns, discussionId, streaming: discStreaming, progress, totalExpectedTurns, summary, summaryLoading, startDiscussion, generateSummary, reset: resetDiscussion } = useDiscussion()

const hasAgents = computed(() => agents.value.length > 0)

/** ディスカッション用: 自分のエージェント + レジストリの公開ペルソナを結合（重複排除） */
const allAvailableAgents = computed(() => {
  const idSet = new Set(agents.value.map(a => a.agent_id))
  const combined = [...agents.value]
  for (const r of registry.value) {
    if (!idSet.has(r.agent_id)) {
      combined.push(r)
    }
  }
  return combined
})

async function loadProfiles() {
  try {
    profiles.value = await apiFetch<{ profile_id: string }[]>('/v1/evolution/profiles')
    if (profiles.value.length === 1) selectedProfileId.value = profiles.value[0].profile_id
  } catch { /* Evolution 未初期化 */ }
}

async function handleCreate() {
  createError.value = null
  if (!newAgentName.value.trim() || !selectedProfileId.value) return
  const agent = await createAgent(selectedProfileId.value, newAgentName.value.trim())
  if (agent) { newAgentName.value = '' } else { createError.value = 'プロファイルが未登録です' }
}

function selectAgent(agent: Agent) {
  selectedAgent.value = agent
  switchThread(null)
  activeTab.value = 'chat'
}

async function handleSend(msg: string) {
  if (!selectedAgent.value) return
  await sendMessage(selectedAgent.value.agent_id, msg)
}

function handleStartDiscussion(agentIds: string[], theme: string) {
  resetDiscussion()
  startDiscussion(agentIds, theme, 5)
}

function openPublishDialog(agent: Agent) {
  publishTargetAgent.value = agent
  showPublishDialog.value = true
}

async function confirmPublish() {
  if (!publishTargetAgent.value) return
  const ok = await publishAgent(publishTargetAgent.value.agent_id)
  if (ok) {
    await listAgents()
    await listRegistry()
  }
  showPublishDialog.value = false
  publishTargetAgent.value = null
}

async function handleUnpublish(agentId: string) {
  await unpublishAgent(agentId)
  await listAgents()
  await listRegistry()
}

/** Agent Pack Zip をダウンロードする */
function downloadPackage(agentId: string) {
  const baseUrl = import.meta.env.VITE_API_URL || '/api'
  const url = `${baseUrl}/v1/evolution/agents/${agentId}/package`
  window.open(url, '_blank')
}

onMounted(async () => {
  await listAgents()
  await listRegistry()
  await loadProfiles()
  const pid = new URLSearchParams(window.location.search).get('profile_id')
  if (pid) selectedProfileId.value = pid
})
</script>

<template>
  <div class="relative min-h-[calc(100vh-52px)] py-8">
    <!-- Ambient glow -->
    <div class="absolute inset-0 -z-10 overflow-hidden pointer-events-none">
      <div class="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full bg-gradient-to-br from-primary/10 to-transparent blur-[120px] animate-float" />
      <div class="absolute bottom-[-10%] right-[-5%] w-[400px] h-[400px] rounded-full bg-gradient-to-tl from-cyan-500/8 to-transparent blur-[100px]" style="animation-delay: -3s" />
    </div>
    <!-- Header -->
    <header class="mb-8">
      <h1 class="text-3xl font-bold tracking-tight gradient-text">Evolution</h1>
      <p class="text-sm text-muted-foreground mt-2">あなたの分身たちが住む世界</p>
    </header>

    <!-- Tab nav -->
    <div class="flex gap-2 mb-6">
      <button
        v-for="tab in ([
          { id: 'agents' as Tab, label: 'エージェント', icon: '◆' },
          { id: 'registry' as Tab, label: 'レジストリ', icon: '◎' },
          { id: 'chat' as Tab, label: 'チャット', icon: '◇' },
          { id: 'discussion' as Tab, label: 'ディスカッション', icon: '△' },
        ])"
        :key="tab.id"
        :class="[
          'px-5 py-2 rounded-xl text-xs font-semibold tracking-wide transition-all duration-300',
          activeTab === tab.id
            ? 'bg-gradient-to-r from-primary to-accent text-white glow'
            : 'glass text-muted-foreground hover:text-foreground'
        ]"
        @click="activeTab = tab.id"
      >
        <span class="mr-1.5 opacity-60">{{ tab.icon }}</span>{{ tab.label }}
      </button>
    </div>

    <!-- ===== AGENTS TAB ===== -->
    <section v-if="activeTab === 'agents'">
      <!-- Create form -->
      <div class="glass rounded-2xl p-6 mb-6">
        <h2 class="text-sm font-bold text-accent mb-4 tracking-wide uppercase">New Agent</h2>
        <div v-if="profiles.length === 0" class="text-sm text-muted-foreground">
          プロファイルが未登録です。
          <router-link to="/survey" class="text-accent underline underline-offset-4 hover:text-primary transition-colors">
            診断を開始
          </router-link>
        </div>
        <div v-else class="flex gap-3">
          <select
            v-model="selectedProfileId"
            class="bg-surface border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:ring-1 focus:ring-primary/50 focus:outline-none min-w-[140px]"
          >
            <option :value="null" disabled>Profile</option>
            <option v-for="p in profiles" :key="p.profile_id" :value="p.profile_id">
              {{ p.profile_id }}
            </option>
          </select>
          <input
            v-model="newAgentName"
            placeholder="名前を入力..."
            class="flex-1 bg-surface border border-border rounded-lg px-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:ring-1 focus:ring-primary/50 focus:outline-none"
            @keydown.enter="handleCreate"
          />
          <button
            :disabled="!newAgentName.trim() || !selectedProfileId"
            class="px-5 py-2 rounded-lg bg-gradient-to-r from-primary to-primary-hover text-white text-sm font-semibold disabled:opacity-30 disabled:cursor-not-allowed hover:glow transition-all"
            @click="handleCreate"
          >
            生成
          </button>
        </div>
        <p v-if="createError" class="text-xs text-red-400 mt-2">{{ createError }}</p>
      </div>

      <!-- Agent grid -->
      <div v-if="agentsLoading" class="text-center py-16 text-muted-foreground text-sm">読み込み中...</div>
      <div v-else-if="!hasAgents" class="text-center py-20">
        <div class="inline-block animate-float">
          <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center text-3xl glow mb-6 mx-auto">
            ◆
          </div>
        </div>
        <p class="text-lg font-semibold">まだ誰もいない</p>
        <p class="text-sm text-muted-foreground mt-2 max-w-xs mx-auto">診断を完了してプロファイルを作成すると、ここに分身が現れます</p>
        <router-link to="/survey" class="inline-block mt-6 px-6 py-2.5 rounded-xl bg-gradient-to-r from-primary to-accent text-white text-sm font-semibold glow hover:scale-105 transition-transform">
          診断を始める
        </router-link>
      </div>
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="agent in agents"
          :key="agent.agent_id"
          class="glass rounded-2xl p-5 cursor-pointer group hover:glow hover:border-primary/20 transition-all duration-300"
          @click="selectAgent(agent)"
        >
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-primary/30 to-accent/20 flex items-center justify-center text-lg font-bold text-accent group-hover:scale-110 transition-transform">
              {{ agent.display_name.charAt(0) }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-sm truncate group-hover:text-accent transition-colors">{{ agent.display_name }}</div>
              <div class="text-[10px] text-muted-foreground mt-0.5 font-mono">{{ agent.profile_id }}</div>
            </div>
            <button
              class="text-[10px] px-2 py-1 rounded-md bg-surface text-muted-foreground hover:bg-surface-hover hover:text-foreground transition-colors"
              @click.stop="downloadPackage(agent.agent_id)"
              title="Agent Pack Zip"
            >
              📦
            </button>
            <button
              class="text-[10px] px-2 py-1 rounded-md bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
              @click.stop="openPublishDialog(agent)"
            >
              公開
            </button>
            <div class="text-muted-foreground group-hover:text-accent group-hover:translate-x-1 transition-all">→</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== REGISTRY TAB ===== -->
    <section v-if="activeTab === 'registry'">
      <div class="glass rounded-2xl p-6 mb-6">
        <h2 class="text-sm font-bold text-accent mb-2 tracking-wide uppercase">Persona Registry</h2>
        <p class="text-xs text-muted-foreground mb-4">公開された分身ペルソナ。チャットや議論の相手として選択できます。</p>
      </div>
      <div v-if="registry.length === 0" class="text-center py-16">
        <p class="text-muted-foreground text-sm">まだ公開されたペルソナはありません</p>
        <p class="text-xs text-muted-foreground mt-2">エージェントタブから分身を公開してください</p>
      </div>
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="agent in registry"
          :key="agent.agent_id"
          class="glass rounded-2xl p-5 cursor-pointer group hover:glow hover:border-cyan-500/20 transition-all duration-300"
          @click="selectAgent(agent)"
        >
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500/30 to-accent/20 flex items-center justify-center text-lg font-bold text-cyan-400 group-hover:scale-110 transition-transform">
              {{ agent.display_name.charAt(0) }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="font-semibold text-sm truncate group-hover:text-cyan-400 transition-colors">{{ agent.display_name }}</div>
              <div class="flex items-center gap-1 mt-0.5">
                <span class="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 font-medium">PUBLIC</span>
              </div>
            </div>
            <div class="text-muted-foreground group-hover:text-cyan-400 group-hover:translate-x-1 transition-all">→</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Publish Confirm Dialog -->
    <Teleport to="body">
      <div v-if="showPublishDialog" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="showPublishDialog = false" />
        <div class="relative glass rounded-2xl p-8 max-w-md w-full mx-4">
          <h3 class="text-lg font-bold mb-3">この分身を公開しますか？</h3>
          <p class="text-sm text-muted-foreground mb-2">
            <strong class="text-accent">{{ publishTargetAgent?.display_name }}</strong> を公開レジストリに登録します。
          </p>
          <p class="text-xs text-muted-foreground mb-6">
            公開されたペルソナは他のユーザーからチャットや議論の相手として選択されるようになります。いつでも非公開に戻せます。
          </p>
          <div class="flex gap-3 justify-end">
            <button
              class="px-4 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground transition-colors"
              @click="showPublishDialog = false"
            >
              キャンセル
            </button>
            <button
              class="px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-accent text-white text-sm font-semibold hover:glow transition-all"
              @click="confirmPublish"
            >
              公開する
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ===== CHAT TAB ===== -->
    <section v-if="activeTab === 'chat'" class="glass rounded-2xl overflow-hidden flex flex-col" style="height: calc(100vh - 320px); min-height: 300px;">
      <template v-if="selectedAgent">
        <!-- Chat header -->
        <div class="flex items-center gap-3 px-5 py-3 border-b border-white/5 shrink-0">
          <div class="w-9 h-9 rounded-lg bg-gradient-to-br from-primary/30 to-accent/20 flex items-center justify-center text-sm font-bold text-accent">
            {{ selectedAgent.display_name.charAt(0) }}
          </div>
          <div class="flex-1">
            <div class="font-semibold text-sm">{{ selectedAgent.display_name }}</div>
            <div class="text-[10px] text-emerald-400 flex items-center gap-1">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block animate-pulse" /> online
            </div>
          </div>
          <button
            class="text-xs text-muted-foreground hover:text-accent px-3 py-1 rounded-lg hover:bg-surface-hover transition-colors"
            @click="activeTab = 'agents'"
          >
            切替
          </button>
        </div>

        <!-- Messages -->
        <div class="flex-1 overflow-y-auto min-h-0">
          <ChatThread :messages="messages" :streaming="streaming" />
        </div>

        <!-- Input -->
        <div class="shrink-0">
          <ChatInput :disabled="chatLoading || streaming" @send="handleSend" />
        </div>
      </template>
      <div v-else class="h-full flex items-center justify-center">
        <div class="text-center">
          <p class="text-muted-foreground text-sm">エージェントを選択してください</p>
          <button class="text-xs text-accent mt-2 hover:underline" @click="activeTab = 'agents'">← 一覧に戻る</button>
        </div>
      </div>
    </section>

    <!-- ===== DISCUSSION TAB ===== -->
    <section v-if="activeTab === 'discussion'">
      <template v-if="!discussionId && !discStreaming">
        <div class="glass rounded-2xl p-6">
          <h2 class="text-sm font-bold text-accent mb-2 tracking-wide uppercase">Multi-Agent Discussion</h2>
          <p class="text-xs text-muted-foreground mb-6">複数の分身にテーマを与え、自律的な議論を観察します</p>
          <DiscussionSetup :agents="allAvailableAgents" @start="handleStartDiscussion" />
          <p v-if="agents.length < 2" class="text-xs text-muted-foreground mt-4">
            ディスカッションには2体以上のエージェントが必要です
          </p>
        </div>
      </template>
      <template v-else>
        <div class="glass rounded-2xl p-4">
          <DiscussionTheater
            :turns="turns"
            :streaming="discStreaming"
            :progress="progress"
            :total-expected-turns="totalExpectedTurns"
          />
        </div>
        <button
          v-if="!discStreaming"
          class="mt-4 px-5 py-2 rounded-xl glass text-sm font-medium text-muted-foreground hover:text-foreground hover:glow-sm transition-all"
          @click="resetDiscussion"
        >
          ↺ 新しいディスカッション
        </button>
        <!-- Insight Summary -->
        <div v-if="!discStreaming" class="mt-4">
          <button
            v-if="!summary"
            :disabled="summaryLoading"
            class="px-5 py-2 rounded-xl bg-gradient-to-r from-primary to-accent text-white text-sm font-semibold disabled:opacity-30 hover:glow transition-all"
            @click="generateSummary"
          >
            {{ summaryLoading ? '分析中...' : '💡 インサイトを抽出' }}
          </button>
          <div v-if="summary" class="glass rounded-2xl p-6 mt-4 space-y-4">
            <h3 class="text-sm font-bold text-accent tracking-wide uppercase">Insights</h3>
            <div v-if="summary.key_insights.length">
              <h4 class="text-xs font-semibold text-foreground mb-2">💡 主要な気づき</h4>
              <ul class="space-y-1">
                <li v-for="(insight, i) in summary.key_insights" :key="i" class="text-xs text-muted-foreground pl-3 border-l-2 border-accent/30">{{ insight }}</li>
              </ul>
            </div>
            <div v-if="summary.disagreements.length">
              <h4 class="text-xs font-semibold text-foreground mb-2">⚡ 対立点</h4>
              <ul class="space-y-1">
                <li v-for="(d, i) in summary.disagreements" :key="i" class="text-xs text-muted-foreground pl-3 border-l-2 border-red-400/30">{{ d }}</li>
              </ul>
            </div>
            <div v-if="summary.unexpected_perspectives.length">
              <h4 class="text-xs font-semibold text-foreground mb-2">🔮 予想外の視点</h4>
              <ul class="space-y-1">
                <li v-for="(p, i) in summary.unexpected_perspectives" :key="i" class="text-xs text-muted-foreground pl-3 border-l-2 border-cyan-400/30">{{ p }}</li>
              </ul>
            </div>
            <div v-if="summary.actionable_suggestions.length">
              <h4 class="text-xs font-semibold text-foreground mb-2">🎯 アクション提案</h4>
              <ul class="space-y-1">
                <li v-for="(s, i) in summary.actionable_suggestions" :key="i" class="text-xs text-muted-foreground pl-3 border-l-2 border-emerald-400/30">{{ s }}</li>
              </ul>
            </div>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>
