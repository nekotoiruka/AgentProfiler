<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import { useTheme } from '@/composables/useTheme'

const route = useRoute()
const currentPath = computed(() => route.path)
const { theme, isDark, cycleTheme } = useTheme()

const themeIcon = computed(() => {
  if (theme.value === 'system') return '◐'
  if (theme.value === 'dark') return '◑'
  return '○'
})

const themeLabel = computed(() => {
  if (theme.value === 'system') return 'System'
  if (theme.value === 'dark') return 'Dark'
  return 'Light'
})

const navLinks = [
  { to: '/survey', label: '診断' },
  { to: '/results', label: '結果' },
  { to: '/evolution', label: 'Evolution' },
] as const
</script>

<template>
  <div id="app-root" class="min-h-screen font-sans bg-[var(--color-background)] text-[var(--color-foreground)] transition-colors duration-300">
    <!-- Nav -->
    <nav class="sticky top-0 z-50 glass">
      <div class="max-w-[1200px] mx-auto flex items-center justify-between px-6 py-3">
        <router-link to="/" class="text-sm font-bold tracking-tight gradient-text">
          Agent Profiler
        </router-link>
        <div class="flex items-center gap-1">
          <router-link
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            :class="[
              'px-4 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
              currentPath === link.to
                ? 'bg-[var(--color-primary-muted)] text-[var(--color-accent)]'
                : 'text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] hover:bg-[var(--color-surface-hover)]'
            ]"
          >
            {{ link.label }}
          </router-link>

          <!-- テーマトグル -->
          <button
            class="ml-3 w-8 h-8 rounded-lg flex items-center justify-center text-sm
                   text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]
                   hover:bg-[var(--color-surface-hover)] transition-all"
            :title="`テーマ: ${themeLabel}`"
            @click="cycleTheme"
          >
            {{ themeIcon }}
          </button>
        </div>
      </div>
    </nav>

    <main class="max-w-[1200px] mx-auto px-6">
      <router-view />
    </main>
  </div>
</template>
