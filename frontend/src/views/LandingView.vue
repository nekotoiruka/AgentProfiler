<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

// --- マウス追従パーティクル ---
const mouseX = ref(50)
const mouseY = ref(50)

function handleMouse(e: MouseEvent) {
  mouseX.value = (e.clientX / window.innerWidth) * 100
  mouseY.value = (e.clientY / window.innerHeight) * 100
}

onMounted(() => {
  window.addEventListener('mousemove', handleMouse)
})
onUnmounted(() => {
  window.removeEventListener('mousemove', handleMouse)
})
</script>

<template>
  <div class="relative min-h-[calc(100vh-52px)] overflow-hidden select-none">
    <!-- マウス追従グロウ -->
    <div
      class="fixed w-[600px] h-[600px] rounded-full pointer-events-none -z-10 transition-all duration-[2000ms] ease-out"
      :style="{
        left: mouseX + '%',
        top: mouseY + '%',
        transform: 'translate(-50%, -50%)',
        background: 'radial-gradient(circle, rgba(109,40,217,0.08) 0%, transparent 70%)',
      }"
    />

    <!-- 固定アンビエント -->
    <div class="absolute inset-0 -z-20 pointer-events-none overflow-hidden">
      <div class="absolute top-[-30%] right-[-10%] w-[800px] h-[800px] rounded-full bg-gradient-to-bl from-primary/6 to-transparent blur-[200px] animate-float" />
      <div class="absolute bottom-[-20%] left-[-5%] w-[500px] h-[500px] rounded-full bg-gradient-to-tr from-cyan-500/5 to-transparent blur-[150px]" style="animation-delay: -4s" />
    </div>

    <!-- Hero セクション -->
    <section class="flex flex-col items-center justify-center min-h-[85vh] px-6 text-center">
      <!-- タイピングアニメーション風ヘッドライン -->
      <p class="text-[11px] tracking-[0.3em] uppercase text-[var(--color-muted-foreground)] mb-10 font-mono">
        think → profile → clone → evolve
      </p>

      <h1 class="text-[clamp(2.5rem,7vw,5rem)] font-black leading-[1.05] tracking-[-0.04em] max-w-4xl">
        <span class="block">あなたの中の</span>
        <span class="block gradient-text">もうひとりの自分</span>
        <span class="block text-[0.6em] font-light tracking-normal text-[var(--color-muted-foreground)] mt-4">
          に、会いにいこう。
        </span>
      </h1>

      <p class="text-sm sm:text-base text-[var(--color-muted-foreground)] max-w-md mx-auto mt-8 leading-[1.8]">
        質問に答えるだけで、あなたの思考回路を持つAIが生まれる。<br />
        そいつと話す。そいつ同士を話させる。<br />
        <strong class="text-[var(--color-foreground)]">自分を客観視する、まったく新しい体験。</strong>
      </p>

      <!-- CTA -->
      <div class="mt-12 flex flex-col sm:flex-row gap-4">
        <router-link
          to="/survey"
          class="group relative inline-flex items-center justify-center px-10 py-4 rounded-2xl bg-gradient-to-r from-primary via-[#a78bfa] to-[#06b6d4] text-white text-sm font-bold tracking-wide overflow-hidden glow hover:scale-[1.03] transition-transform"
        >
          <span class="relative z-10">自分を解析する</span>
          <div class="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity" />
        </router-link>
        <router-link
          to="/evolution"
          class="inline-flex items-center justify-center px-8 py-4 rounded-2xl glass text-sm font-medium text-[var(--color-foreground)] hover:glow-sm transition-all"
        >
          分身たちの世界を覗く
        </router-link>
      </div>
    </section>

    <!-- What happens セクション -->
    <section class="px-6 pb-24">
      <div class="max-w-3xl mx-auto">
        <h2 class="text-center text-xs tracking-[0.25em] uppercase text-[var(--color-muted-foreground)] mb-12 font-mono">
          what happens here
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="glass rounded-2xl p-6 hover:glow transition-all duration-500 group">
            <div class="text-3xl mb-4 group-hover:scale-110 transition-transform">🧠</div>
            <h3 class="text-sm font-bold mb-2">思考をスキャン</h3>
            <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">
              47問の質問があなたの意思決定パターン・価値観・こだわりを4軸で数値化する。所要15分。
            </p>
          </div>
          <div class="glass rounded-2xl p-6 hover:glow transition-all duration-500 group">
            <div class="text-3xl mb-4 group-hover:scale-110 transition-transform">⚡</div>
            <h3 class="text-sm font-bold mb-2">分身が生まれる</h3>
            <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">
              プロファイルからAIエージェントを生成。あなたの口調・判断軸・禁止事項を内蔵した分身。
            </p>
          </div>
          <div class="glass rounded-2xl p-6 hover:glow transition-all duration-500 group">
            <div class="text-3xl mb-4 group-hover:scale-110 transition-transform">🎭</div>
            <h3 class="text-sm font-bold mb-2">分身同士が議論する</h3>
            <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">
              複数の分身にテーマを投げると、勝手に議論が始まる。自分の中の多面性を目撃する体験。
            </p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
