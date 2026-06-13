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
  <div id="app-root" class="min-h-screen font-sans">
    <!-- Nav -->
    <nav class="sticky top-0 z-50 bg-white backdrop-blur-xl border-b border-zinc-200">
      <div class="max-w-[1200px] mx-auto flex items-center justify-between px-6 py-3">
        <router-link to="/" class="text-sm font-bold tracking-tight text-violet-700">
          Agent Profiler
        </router-link>
        <div class="flex gap-1">
          <router-link
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            :class="[
              'px-4 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
              currentPath === link.to
                ? 'bg-violet-100 text-violet-700'
                : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100'
            ]"
          >
            {{ link.label }}
          </router-link>
        </div>
      </div>
    </nav>

    <main class="max-w-[1200px] mx-auto px-6">
      <router-view />
    </main>
  </div>
</template>
