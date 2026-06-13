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
  <div id="app-root" class="min-h-screen bg-background text-foreground font-sans">
    <!-- Ambient background glow -->
    <div class="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      <div class="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full bg-gradient-to-br from-primary/10 to-transparent blur-[120px] animate-float" />
      <div class="absolute bottom-[-10%] right-[-5%] w-[400px] h-[400px] rounded-full bg-gradient-to-tl from-cyan-500/8 to-transparent blur-[100px]" style="animation-delay: -3s" />
    </div>

    <!-- Nav -->
    <nav class="sticky top-0 z-50 glass border-b border-white/5">
      <div class="max-w-[1200px] mx-auto flex items-center justify-between px-6 py-3">
        <router-link to="/" class="text-sm font-bold tracking-tight gradient-text">
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
                ? 'bg-primary/15 text-accent glow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-surface-hover'
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
