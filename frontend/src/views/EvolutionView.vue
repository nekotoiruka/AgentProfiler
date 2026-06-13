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

type Tab = 'agents' | 'chat' | 'discussion'
const activeTab = ref<Tab>('agents')

const { agents, loading: agentsLoading, listAgents, createAgent } = useAgents()
const profiles = ref<{ profile_id: string }[]>([])
const selectedProfileId = ref<string | null>(null)
const newAgentName = ref('')
const createError = ref<string | null>(null)

const selectedAgent = ref<Agent | null>(null)
const { messages, streaming, loading: chatLoading, sendMessage, switchThread } = useChat()
const { turns, discussionId, streaming: discStreaming, progress, totalExpectedTurns, startDiscussion, reset: resetDiscussion } = useDiscussion()

const hasAgents = computed(() => agents.value.length > 0)

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

onMounted(async () => {
  await listAgents()
  await loadProfiles()
  const pid = new URLSearchParams(window.location.search).get('profile_id')
  if (pid) selectedProfileId.value = pid
})
</script>

<template>
  <div class="relative min-h-[calc(100vh-52px)] bg-background text-foreground py-8">
    <!-- Ambient background glow (Evolution 限定) -->
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
            <div class="text-muted-foreground group-hover:text-accent group-hover:translate-x-1 transition-all">→</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===== CHAT TAB ===== -->
    <section v-if="activeTab === 'chat'" class="glass rounded-2xl overflow-hidden" style="height: calc(100vh - 240px); min-height: 400px;">
      <template v-if="selectedAgent">
        <!-- Chat header -->
        <div class="flex items-center gap-3 px-5 py-3 border-b border-white/5">
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
        <div class="flex-1 overflow-y-auto" style="height: calc(100% - 120px);">
          <ChatThread :messages="messages" :streaming="streaming" />
        </div>

        <!-- Input -->
        <ChatInput :disabled="chatLoading || streaming" @send="handleSend" />
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
          <DiscussionSetup :agents="agents" @start="handleStartDiscussion" />
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
      </template>
    </section>
  </div>
</template>
