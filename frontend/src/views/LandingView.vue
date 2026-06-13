<script setup lang="ts">
</script>

<template>
  <div class="relative min-h-[calc(100vh-52px)] flex flex-col items-center justify-center overflow-hidden px-6">
    <!-- Ambient orbs -->
    <div class="absolute inset-0 -z-10 pointer-events-none">
      <div class="absolute top-[10%] left-[20%] w-[500px] h-[500px] rounded-full bg-gradient-to-br from-primary/15 to-transparent blur-[150px] animate-float" />
      <div class="absolute bottom-[5%] right-[15%] w-[350px] h-[350px] rounded-full bg-gradient-to-tl from-cyan-500/10 to-transparent blur-[120px]" style="animation-delay: -2s" />
      <div class="absolute top-[50%] left-[60%] w-[200px] h-[200px] rounded-full bg-gradient-to-r from-pink-500/8 to-transparent blur-[80px]" style="animation-delay: -4s" />
    </div>

    <!-- Hero -->
    <div class="text-center max-w-2xl mx-auto">
      <!-- Badge -->
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full glass text-[10px] font-medium tracking-widest uppercase text-[var(--color-muted-foreground)] mb-8">
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        AI-Powered Agent Creation
      </div>

      <!-- Headline -->
      <h1 class="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight leading-[1.1] mb-6">
        <span class="gradient-text">あなたの分身</span>を<br />
        つくる。動かす。観察する。
      </h1>

      <!-- Sub -->
      <p class="text-base sm:text-lg text-[var(--color-muted-foreground)] max-w-lg mx-auto leading-relaxed mb-10">
        47の質問であなたの思考特性を解析し、パーソナライズされたAIエージェントを生成。分身同士の対話から、新たな自分を発見する。
      </p>

      <!-- CTA -->
      <div class="flex flex-col sm:flex-row gap-3 justify-center">
        <router-link
          to="/survey"
          class="inline-flex items-center justify-center px-8 py-3.5 rounded-xl bg-gradient-to-r from-primary to-[#a78bfa] text-white text-sm font-semibold tracking-wide glow hover:scale-[1.02] transition-transform"
        >
          診断を始める →
        </router-link>
        <router-link
          to="/evolution"
          class="inline-flex items-center justify-center px-8 py-3.5 rounded-xl glass text-sm font-medium text-[var(--color-foreground)] hover:glow-sm transition-all"
        >
          Evolution を見る
        </router-link>
      </div>
    </div>

    <!-- Features -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-20 w-full max-w-3xl">
      <div class="glass rounded-2xl p-5 text-center">
        <div class="text-2xl mb-2">◆</div>
        <h3 class="text-sm font-semibold mb-1">思考特性の可視化</h3>
        <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">独自の4軸モデルであなたの意思決定パターンを数値化</p>
      </div>
      <div class="glass rounded-2xl p-5 text-center">
        <div class="text-2xl mb-2">◇</div>
        <h3 class="text-sm font-semibold mb-1">分身エージェント生成</h3>
        <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">プロファイルからAI分身を生成し、チャットや議論が可能</p>
      </div>
      <div class="glass rounded-2xl p-5 text-center">
        <div class="text-2xl mb-2">△</div>
        <h3 class="text-sm font-semibold mb-1">マルチエージェント対話</h3>
        <p class="text-[11px] text-[var(--color-muted-foreground)] leading-relaxed">複数の分身がテーマについて自律議論。新たな視点を発見</p>
      </div>
    </div>
  </div>
</template>
