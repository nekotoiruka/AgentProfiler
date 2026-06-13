<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()
const currentPath = computed(() => route.path)
</script>

<template>
  <div id="app-root">
    <!-- グローバルナビゲーション -->
    <nav class="app-nav">
      <div class="app-nav__brand">Agent Profiler</div>
      <div class="app-nav__links">
        <router-link
          to="/survey"
          :class="['app-nav__link', { active: currentPath === '/survey' }]"
        >
          診断
        </router-link>
        <router-link
          to="/results"
          :class="['app-nav__link', { active: currentPath === '/results' }]"
        >
          結果
        </router-link>
        <router-link
          to="/evolution"
          :class="['app-nav__link', { active: currentPath === '/evolution' }]"
        >
          Evolution
        </router-link>
      </div>
    </nav>

    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<style>
* { box-sizing: border-box; }

body {
  margin: 0;
  background: #fafbfc;
}

#app-root {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  color: #1a1a2e;
  min-height: 100vh;
}

.app-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 2rem;
  background: white;
  border-bottom: 1px solid #e2e8f0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.app-nav__brand {
  font-size: 1rem;
  font-weight: 700;
  color: #6d28d9;
  letter-spacing: -0.02em;
}

.app-nav__links {
  display: flex;
  gap: 0.25rem;
}

.app-nav__link {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.8125rem;
  font-weight: 500;
  color: #64748b;
  text-decoration: none;
  transition: all 0.15s;
}

.app-nav__link:hover {
  color: #1a1a2e;
  background: #f1f5f9;
}

.app-nav__link.active {
  color: #6d28d9;
  background: #ede9fe;
}

.app-main {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 1.5rem;
}
</style>
