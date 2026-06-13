# Design Document: Frontend Design System

## Overview

Tailwind CSS v4 + shadcn-vue を基盤としたフロントエンドデザインシステムの導入と、Evolution ページの 3 タブ構成でのフルリビルド。既存ページ（SurveyView, ResultsDashboardView）には手を加えず、段階的にデザインシステムを適用する。

## Architecture

### レイヤー構成

```
src/
├── assets/
│   └── styles/
│       └── globals.css          # Tailwind ディレクティブ + CSS 変数テーマ
├── components/
│   └── ui/                      # shadcn-vue コンポーネント（自動生成）
│       ├── button/
│       ├── card/
│       ├── tabs/
│       ├── input/
│       ├── select/
│       ├── avatar/
│       ├── badge/
│       ├── scroll-area/
│       └── sheet/
├── components/
│   └── evolution/               # Evolution ページ専用コンポーネント
│       ├── AgentsTab.vue
│       ├── ChatTab.vue
│       ├── DiscussionTab.vue
│       ├── AgentDrawer.vue
│       ├── ChatThread.vue
│       ├── ChatInput.vue
│       ├── DiscussionSetup.vue
│       ├── DiscussionTheater.vue
│       ├── TurnBubble.vue
│       └── composables/
│           ├── useAgents.ts
│           ├── useChat.ts
│           └── useDiscussion.ts
├── views/
│   ├── EvolutionView.vue        # タブコンテナ（リビルド対象）
│   ├── SurveyView.vue           # 変更なし
│   └── ResultsDashboardView.vue # 変更なし
└── App.vue                      # グローバルナビ（Tailwind 移行）
```

### 技術スタック

| レイヤー | 技術 | バージョン |
|---------|------|-----------|
| フレームワーク | Vue 3 (Composition API) | 3.5.x |
| ビルド | Vite | 6.x |
| 型システム | TypeScript | 5.7.x |
| 状態管理 | Pinia | 2.3.x |
| ルーティング | Vue Router | 4.5.x |
| CSS | Tailwind CSS | v4 |
| UIライブラリ | shadcn-vue | latest |
| テスト | Vitest + @vue/test-utils | 3.x / 2.x |

## Components

### 1. Tailwind CSS + shadcn-vue セットアップ

```typescript
// vite.config.ts — Tailwind v4 は @tailwindcss/vite プラグインで統合
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
  },
})
```

```css
/* src/assets/styles/globals.css */
@import "tailwindcss";

@theme {
  --color-primary: #6d28d9;
  --color-primary-foreground: #ffffff;
  --color-primary-hover: #5b21b6;
  --color-primary-muted: #ede9fe;

  --color-background: #fafbfc;
  --color-foreground: #1a1a2e;
  --color-muted: #f1f5f9;
  --color-muted-foreground: #64748b;
  --color-border: #e2e8f0;
  --color-card: #ffffff;
  --color-accent: #6d28d9;
  --color-accent-foreground: #ffffff;

  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
}
```

### 2. App.vue — グローバルナビゲーション

```vue
<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()
const currentPath = computed(() => route.path)

const navLinks = [
  { to: '/survey', label: '診断' },
  { to: '/results', label: '結果' },
  { to: '/evolution', label: 'Evolution' },
] as const
</script>

<template>
  <div id="app-root" class="min-h-screen font-sans text-foreground bg-background">
    <nav class="sticky top-0 z-50 flex items-center justify-between px-8 py-3
                bg-card border-b border-border">
      <div class="text-base font-bold text-primary tracking-tight">
        Agent Profiler
      </div>
      <div class="flex gap-1">
        <router-link
          v-for="link in navLinks"
          :key="link.to"
          :to="link.to"
          :class="[
            'px-4 py-2 rounded-md text-sm font-medium transition-colors',
            currentPath === link.to
              ? 'text-primary bg-primary-muted'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          ]"
        >
          {{ link.label }}
        </router-link>
      </div>
    </nav>

    <main class="max-w-[1080px] mx-auto px-6">
      <router-view />
    </main>
  </div>
</template>
```

### 3. EvolutionView.vue — タブコンテナ

```vue
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import AgentsTab from '@/components/evolution/AgentsTab.vue'
import ChatTab from '@/components/evolution/ChatTab.vue'
import DiscussionTab from '@/components/evolution/DiscussionTab.vue'
import { useAgents, type Agent } from '@/components/evolution/composables/useAgents'
import { apiFetch } from '@/composables/useApi'

const activeTab = ref('agents')

const { agents, loading: agentsLoading, listAgents, createAgent } = useAgents()
const profiles = ref<{ profile_id: string }[]>([])
const selectedAgent = ref<Agent | null>(null)

async function loadProfiles() {
  try {
    profiles.value = await apiFetch<{ profile_id: string }[]>('/v1/evolution/profiles')
  } catch {
    // Evolution 未初期化時は空
  }
}

function handleSelectAgent(agent: Agent) {
  selectedAgent.value = agent
  activeTab.value = 'chat'
}

onMounted(async () => {
  await listAgents()
  await loadProfiles()
  const params = new URLSearchParams(window.location.search)
  const pid = params.get('profile_id')
  if (pid) {
    // URL パラメータによる自動選択ロジック
  }
})
</script>

<template>
  <div class="py-6">
    <header class="mb-6">
      <h1 class="text-2xl font-bold tracking-tight">Agent Evolution</h1>
      <p class="text-sm text-muted-foreground mt-1">あなたの分身たちと対話する</p>
    </header>

    <Tabs v-model="activeTab" default-value="agents" class="w-full">
      <TabsList class="grid w-full grid-cols-3">
        <TabsTrigger value="agents">エージェント</TabsTrigger>
        <TabsTrigger value="chat">チャット</TabsTrigger>
        <TabsTrigger value="discussion">ディスカッション</TabsTrigger>
      </TabsList>

      <TabsContent value="agents">
        <AgentsTab
          :agents="agents"
          :profiles="profiles"
          :loading="agentsLoading"
          @select="handleSelectAgent"
          @create="createAgent"
        />
      </TabsContent>

      <TabsContent value="chat">
        <ChatTab
          :agents="agents"
          :selected-agent="selectedAgent"
          @switch-agent="handleSelectAgent"
        />
      </TabsContent>

      <TabsContent value="discussion">
        <DiscussionTab :agents="agents" />
      </TabsContent>
    </Tabs>
  </div>
</template>
```

### 4. AgentsTab.vue

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { Card, CardContent } from '@/components/ui/card'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/components/ui/select'
import type { Agent } from '@/components/evolution/composables/useAgents'

interface Props {
  agents: Agent[]
  profiles: { profile_id: string }[]
  loading: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  select: [agent: Agent]
  create: [profileId: string, displayName: string]
}>()

const newAgentName = ref('')
const selectedProfileId = ref<string | null>(null)

function handleCreate() {
  if (!newAgentName.value.trim() || !selectedProfileId.value) return
  emit('create', selectedProfileId.value, newAgentName.value.trim())
  newAgentName.value = ''
}
</script>

<template>
  <div class="space-y-6 pt-4">
    <!-- 新規作成フォーム -->
    <div>
      <h2 class="text-lg font-semibold mb-2">新しいエージェントを作成</h2>
      <div v-if="profiles.length === 0" class="text-sm text-muted-foreground">
        プロファイルが登録されていません。
        <router-link to="/survey" class="text-primary underline">
          質問フローを完了
        </router-link>してください。
      </div>
      <div v-else class="flex gap-2 mt-3">
        <Select v-model="selectedProfileId">
          <SelectTrigger class="w-[180px]">
            <SelectValue placeholder="プロファイルを選択" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="p in profiles"
              :key="p.profile_id"
              :value="p.profile_id"
            >
              {{ p.profile_id }}
            </SelectItem>
          </SelectContent>
        </Select>
        <Input
          v-model="newAgentName"
          placeholder="エージェント名"
          class="flex-1"
          @keydown.enter="handleCreate"
        />
        <Button
          :disabled="!newAgentName.trim() || !selectedProfileId"
          @click="handleCreate"
        >
          作成
        </Button>
      </div>
    </div>

    <!-- エージェント一覧 -->
    <div v-if="loading" class="text-center py-8 text-muted-foreground">
      読み込み中...
    </div>
    <div v-else-if="agents.length === 0" class="text-center py-16">
      <div class="text-5xl mb-4">🤖</div>
      <p class="text-lg font-semibold">まだエージェントがいません</p>
      <p class="text-sm text-muted-foreground mt-2 max-w-sm mx-auto">
        質問フローを完了してプロファイルを作成し、分身エージェントを生成しましょう
      </p>
      <Button as-child class="mt-4">
        <router-link to="/survey">質問フローを始める</router-link>
      </Button>
    </div>
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <Card
        v-for="agent in agents"
        :key="agent.agent_id"
        class="cursor-pointer hover:border-primary/30 hover:shadow-sm transition-all"
        @click="emit('select', agent)"
      >
        <CardContent class="flex items-center gap-3 p-4">
          <Avatar class="size-10">
            <AvatarFallback class="bg-primary-muted text-primary font-bold">
              {{ agent.display_name.charAt(0) }}
            </AvatarFallback>
          </Avatar>
          <div class="flex-1 min-w-0">
            <div class="font-semibold text-sm truncate">
              {{ agent.display_name }}
            </div>
            <div class="text-xs text-muted-foreground mt-0.5">
              {{ agent.profile_id }}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
```

### 5. ChatTab.vue

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import AgentDrawer from './AgentDrawer.vue'
import ChatThread from './ChatThread.vue'
import { useChat } from './composables/useChat'
import type { Agent } from './composables/useAgents'

interface Props {
  agents: Agent[]
  selectedAgent: Agent | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'switch-agent': [agent: Agent]
}>()

const { messages, streaming, loading, sendMessage, switchThread } = useChat()
const drawerOpen = ref(false)

async function handleSend(message: string) {
  if (!props.selectedAgent) return
  await sendMessage(props.selectedAgent.agent_id, message)
}

function handleAgentSwitch(agent: Agent) {
  emit('switch-agent', agent)
  switchThread(null)
  drawerOpen.value = false
}
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-220px)] min-h-[400px]">
    <!-- ヘッダー -->
    <div v-if="selectedAgent"
         class="flex items-center gap-3 px-4 py-3 border-b border-border">
      <Button variant="ghost" size="icon" @click="drawerOpen = true">
        ☰
      </Button>
      <Avatar class="size-9">
        <AvatarFallback class="bg-primary-muted text-primary font-bold text-sm">
          {{ selectedAgent.display_name.charAt(0) }}
        </AvatarFallback>
      </Avatar>
      <div>
        <div class="font-semibold text-sm">{{ selectedAgent.display_name }}</div>
        <div class="text-xs text-emerald-500">オンライン</div>
      </div>
    </div>

    <!-- メッセージ一覧 -->
    <ScrollArea v-if="selectedAgent" class="flex-1 px-4 py-3">
      <ChatThread :messages="messages" :streaming="streaming" />
    </ScrollArea>

    <!-- プレースホルダー -->
    <div v-else class="flex-1 flex items-center justify-center text-muted-foreground text-sm">
      エージェントを選択してください
    </div>

    <!-- 入力エリア -->
    <ChatInput
      v-if="selectedAgent"
      :disabled="loading || streaming"
      @send="handleSend"
    />

    <!-- エージェント切り替えドロワー -->
    <AgentDrawer
      :open="drawerOpen"
      :agents="agents"
      :selected-agent="selectedAgent"
      @update:open="drawerOpen = $event"
      @select="handleAgentSwitch"
    />
  </div>
</template>
```

### 6. AgentDrawer.vue

```vue
<script setup lang="ts">
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from '@/components/ui/sheet'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import type { Agent } from './composables/useAgents'

interface Props {
  open: boolean
  agents: Agent[]
  selectedAgent: Agent | null
}

defineProps<Props>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  select: [agent: Agent]
}>()
</script>

<template>
  <Sheet :open="open" @update:open="emit('update:open', $event)">
    <SheetContent side="left" class="w-72">
      <SheetHeader>
        <SheetTitle>エージェント切り替え</SheetTitle>
      </SheetHeader>
      <div class="mt-4 space-y-1">
        <div
          v-for="agent in agents"
          :key="agent.agent_id"
          class="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer
                 hover:bg-muted transition-colors"
          @click="emit('select', agent)"
        >
          <Avatar class="size-8">
            <AvatarFallback class="bg-primary-muted text-primary text-xs font-semibold">
              {{ agent.display_name.charAt(0) }}
            </AvatarFallback>
          </Avatar>
          <span class="text-sm font-medium flex-1">{{ agent.display_name }}</span>
          <Badge
            v-if="selectedAgent?.agent_id === agent.agent_id"
            variant="secondary"
          >
            選択中
          </Badge>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>
```

### 7. DiscussionTab.vue

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { Button } from '@/components/ui/button'
import DiscussionSetup from './DiscussionSetup.vue'
import DiscussionTheater from './DiscussionTheater.vue'
import { useDiscussion } from './composables/useDiscussion'
import type { Agent } from './composables/useAgents'

interface Props {
  agents: Agent[]
}

const props = defineProps<Props>()

const {
  turns, discussionId, streaming, progress, totalExpectedTurns,
  startDiscussion, reset,
} = useDiscussion()

const hasEnoughAgents = computed(() => props.agents.length >= 2)

function handleStart(agentIds: string[], theme: string) {
  reset()
  startDiscussion(agentIds, theme, 5)
}
</script>

<template>
  <div class="pt-4">
    <template v-if="!discussionId && !streaming">
      <h2 class="text-lg font-semibold">マルチエージェント・ディスカッション</h2>
      <p class="text-sm text-muted-foreground mt-1 mb-6">
        複数のエージェントにテーマを与えて、議論を観察しましょう。
      </p>
      <DiscussionSetup :agents="agents" @start="handleStart" />
      <p v-if="!hasEnoughAgents" class="text-sm text-muted-foreground mt-3">
        ディスカッションには2体以上のエージェントが必要です。
      </p>
    </template>
    <template v-else>
      <DiscussionTheater
        :turns="turns"
        :streaming="streaming"
        :progress="progress"
        :total-expected-turns="totalExpectedTurns"
      />
      <Button
        v-if="!streaming"
        variant="outline"
        class="mt-4"
        @click="reset"
      >
        新しいディスカッションを開始
      </Button>
    </template>
  </div>
</template>
```

## Interfaces

### コンポーネント Props / Emits

```typescript
// AgentsTab
interface AgentsTabProps {
  agents: Agent[]
  profiles: { profile_id: string }[]
  loading: boolean
}
interface AgentsTabEmits {
  select: [agent: Agent]
  create: [profileId: string, displayName: string]
}

// ChatTab
interface ChatTabProps {
  agents: Agent[]
  selectedAgent: Agent | null
}
interface ChatTabEmits {
  'switch-agent': [agent: Agent]
}

// AgentDrawer
interface AgentDrawerProps {
  open: boolean
  agents: Agent[]
  selectedAgent: Agent | null
}
interface AgentDrawerEmits {
  'update:open': [value: boolean]
  select: [agent: Agent]
}

// DiscussionTab
interface DiscussionTabProps {
  agents: Agent[]
}
```

### 既存 Composable インターフェース（変更なし）

```typescript
// useAgents.ts
interface Agent {
  agent_id: string
  profile_id: string
  display_name: string
  created_at: string
  is_active: boolean
}

// useChat.ts — 既存のまま利用
function useChat(): {
  messages: Ref<ChatMessage[]>
  threadId: Ref<string | null>
  loading: Ref<boolean>
  streaming: Ref<boolean>
  sendMessage: (agentId: string, message: string) => Promise<void>
  switchThread: (threadId: string | null) => void
}

// useDiscussion.ts — 既存のまま利用
function useDiscussion(): {
  turns: Ref<DiscussionTurn[]>
  discussionId: Ref<string | null>
  streaming: Ref<boolean>
  progress: Ref<number>
  totalExpectedTurns: Ref<number>
  startDiscussion: (agentIds: string[], theme: string, maxTurns: number) => void
  reset: () => void
}
```

## Data Models

既存のデータモデル（Agent, ChatMessage, DiscussionTurn）に変更は不要。UI コンポーネント層の刷新のみ。

```typescript
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

interface DiscussionTurn {
  agent_id: string
  display_name: string
  content: string
  turn_number: number
}
```

## Error Handling

| シナリオ | 処理 |
|---------|------|
| API 通信エラー（エージェント取得） | ローディング解除 + error 状態表示 |
| エージェント作成失敗 | createError メッセージ表示（フォームはリセットしない） |
| プロファイル未登録 | 質問フローへのリンク付き誘導メッセージ |
| エージェント 0 件 | 空状態 UI + 質問フロー開始ボタン |
| チャット送信失敗 | メッセージリストにエラー表示（useChat 内で処理） |
| ストリーミング中の再送信防止 | Input + Button を disabled |

## Tailwind プレフライト共存戦略

Tailwind CSS v4 ではプレフライト（リセット CSS）がデフォルトで含まれる。既存ページへの影響を防ぐため：

1. **`@layer base` でのスコーピング不要** — Tailwind v4 のプレフライトは軽量で、既存の `SurveyView` / `ResultsDashboardView` は scoped style を持つためオーバーライドされない
2. 既存ページが独自の `<style scoped>` を持つ場合、Vue の scoped CSS が優先される
3. 万一レイアウト崩れが発生した場合は `@import "tailwindcss" layer(tailwind)` でレイヤー分離する

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Active nav link corresponds to current route

*For any* valid route path from the set {'/survey', '/results', '/evolution'}, only the router-link whose `to` attribute matches the current route should have the active indicator class applied.

**Validates: Requirements 2.4**

### Property 2: Tab exclusivity

*For any* tab value from the set {'agents', 'chat', 'discussion'}, when that tab is active, only its corresponding TabsContent is rendered and the other two are hidden.

**Validates: Requirements 3.2**

### Property 3: Agent card rendering fidelity

*For any* non-empty list of agents, the AgentsTab renders exactly N Card components each containing the first character of `display_name` as avatar text, the full `display_name`, and the `profile_id`.

**Validates: Requirements 4.1, 4.2**

### Property 4: Agent card click navigates to chat

*For any* agent in a non-empty list, clicking that agent's card sets the active tab to 'chat' and sets the selected agent to the clicked agent.

**Validates: Requirements 4.3**

### Property 5: Chat input disabled during streaming or loading

*For any* combination of states where `streaming === true` OR `loading === true`, the chat input form (Input + Button) is in a disabled state.

**Validates: Requirements 5.4**

### Property 6: Drawer agent selection closes drawer and switches context

*For any* agent in the drawer list, clicking that agent sets `selectedAgent` to the clicked agent and closes the drawer (`open` becomes `false`).

**Validates: Requirements 6.4**

### Property 7: Badge highlights only the selected agent in drawer

*For any* selected agent, within the AgentDrawer, only the entry matching the selected agent's `agent_id` should display the Badge component. All other entries should have no Badge.

**Validates: Requirements 6.5**

### Property 8: Discussion turns rendering completeness

*For any* list of N discussion turns (whether streaming or completed), the DiscussionTheater renders exactly N turn entries. When streaming is false (completed), the "new discussion" button is enabled.

**Validates: Requirements 7.2, 7.3**
