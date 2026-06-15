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
      <p class="text-[11px] tracking-[0.3em] uppercase text-[var(--color-muted-foreground)] mb-10 font-mono">
        answer → structure → clone → evolve
      </p>

      <h1 class="text-[clamp(2.5rem,7vw,4.5rem)] font-black leading-[1.05] tracking-[-0.04em] max-w-4xl">
        <span class="block">質問に答えるだけで</span>
        <span class="block gradient-text">判断まで再現する</span>
        <span class="block">AI分身が生まれる。</span>
      </h1>

      <p class="text-sm sm:text-base text-[var(--color-muted-foreground)] max-w-lg mx-auto mt-8 leading-[1.8]">
        88問の質問で、あなたの<strong class="text-[var(--color-foreground)]">優先順位・トレードオフ傾向・失敗パターン・状況適応</strong>を構造化。<br />
        口調だけでなく、<strong class="text-[var(--color-foreground)]">判断のアルゴリズムそのもの</strong>を内蔵したエージェントを生成します。
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

    <!-- 6層モデル解説セクション -->
    <section class="px-6 pb-20">
      <div class="max-w-4xl mx-auto">
        <h2 class="text-center text-xs tracking-[0.25em] uppercase text-[var(--color-muted-foreground)] mb-4 font-mono">
          6-layer agent model
        </h2>
        <p class="text-center text-sm text-[var(--color-muted-foreground)] mb-12 max-w-2xl mx-auto leading-relaxed">
          人間の判断プロセスを6層に分解し、各層を独立に構造化してエージェントに埋め込みます。<br />
          従来のパーソナライズが「口調」だけだったのに対し、<strong class="text-[var(--color-foreground)]">判断層を中心に全6層を実装</strong>します。
        </p>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <!-- Layer 6 -->
          <div class="glass rounded-2xl p-5 hover:glow transition-all duration-500 group border-l-4 border-cyan-400/50">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-xs font-mono text-cyan-400">L6</span>
              <h3 class="text-sm font-bold">改善 (Improvement)</h3>
            </div>
            <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">
              失敗パターンの認識と自己学習。使うほど精度が上がるフィードバックループ。
            </p>
          </div>
          <!-- Layer 5 -->
          <div class="glass rounded-2xl p-5 hover:glow transition-all duration-500 group border-l-4 border-blue-400/50">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-xs font-mono text-blue-400">L5</span>
              <h3 class="text-sm font-bold">境界 (Boundary)</h3>
            </div>
            <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">
              権限とエスカレーションの安全装置。「やっていいか、聞くべきか」を自律判断する。
            </p>
          </div>
          <!-- Layer 4 -->
          <div class="glass rounded-2xl p-5 hover:glow transition-all duration-500 group border-l-4 border-indigo-400/50">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-xs font-mono text-indigo-400">L4</span>
              <h3 class="text-sm font-bold">行動 (Action)</h3>
            </div>
            <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">
              状況依存のモード切り替えと実行。経営報告 / チーム指示 / 緊急対応で自動的にトーンを変える。
            </p>
          </div>
          <!-- Layer 3 (最重要) -->
          <div class="glass rounded-2xl p-5 hover:glow transition-all duration-500 group border-l-4 border-violet-500 ring-1 ring-violet-500/20">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-xs font-mono text-violet-400 font-bold">L3</span>
              <h3 class="text-sm font-bold">判断 (Decision) <span class="text-[10px] text-violet-400">★最重要</span></h3>
            </div>
            <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">
              トレードオフ解消と優先順位付け。「品質 vs スピード」「自律 vs 合意」で<strong>あなたと同じ側を選ぶ</strong>。
            </p>
          </div>
          <!-- Layer 2 -->
          <div class="glass rounded-2xl p-5 hover:glow transition-all duration-500 group border-l-4 border-slate-400/50">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-xs font-mono text-slate-400">L2</span>
              <h3 class="text-sm font-bold">知識 (Knowledge)</h3>
            </div>
            <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">
              専門知識、経験則、思考OS。4軸の思考特性スコアとして定量化。
            </p>
          </div>
          <!-- Layer 1 -->
          <div class="glass rounded-2xl p-5 hover:glow transition-all duration-500 group border-l-4 border-slate-400/50">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-xs font-mono text-slate-400">L1</span>
              <h3 class="text-sm font-bold">人格 (Personality)</h3>
            </div>
            <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">
              価値観、口調、ベースとなる雰囲気。一人称・敬語レベル・ユーモア傾向まで再現。
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 仕組みセクション -->
    <section class="px-6 pb-24">
      <div class="max-w-3xl mx-auto">
        <h2 class="text-center text-xs tracking-[0.25em] uppercase text-[var(--color-muted-foreground)] mb-12 font-mono">
          how it works
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-5">
          <div class="glass rounded-2xl p-5 hover:glow transition-all duration-500 group text-center">
            <div class="text-2xl mb-3">📝</div>
            <h3 class="text-xs font-bold mb-2">88問に回答</h3>
            <p class="text-[10px] text-[var(--color-muted-foreground)] leading-relaxed">
              4択 / 2択トレードオフ / ドラッグ&ドロップ順序付け。20分で完了。
            </p>
          </div>
          <div class="glass rounded-2xl p-5 hover:glow transition-all duration-500 group text-center">
            <div class="text-2xl mb-3">⚙️</div>
            <h3 class="text-xs font-bold mb-2">3層パイプラインで変換</h3>
            <p class="text-[10px] text-[var(--color-muted-foreground)] leading-relaxed">
              回答 → 正規化タグ → 実行可能ルール。全回答を「when_X: Y」形式のポリシーに変換。
            </p>
          </div>
          <div class="glass rounded-2xl p-5 hover:glow transition-all duration-500 group text-center">
            <div class="text-2xl mb-3">🏗️</div>
            <h3 class="text-xs font-bold mb-2">Rule Hierarchy に集約</h3>
            <p class="text-[10px] text-[var(--color-muted-foreground)] leading-relaxed">
              全ルールを4層に優先順位付け。矛盾するルールがあっても上位層が勝つ。
            </p>
          </div>
          <div class="glass rounded-2xl p-5 hover:glow transition-all duration-500 group text-center">
            <div class="text-2xl mb-3">🤖</div>
            <h3 class="text-xs font-bold mb-2">分身エージェント誕生</h3>
            <p class="text-[10px] text-[var(--color-muted-foreground)] leading-relaxed">
              6層プロファイルをシステムプロンプトに変換。チャット・議論・フィードバックで成長。
            </p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
