/**
 * テーマ管理 composable
 *
 * - デフォルト: OS のシステム設定 (prefers-color-scheme) に追従
 * - ユーザーが手動で切り替え可能
 * - 選択は localStorage に保存
 * - <html> 要素に 'dark' クラスを付与/除去で制御
 */

import { ref, watchEffect, onMounted } from 'vue'

type Theme = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'agent-profiler-theme'

const theme = ref<Theme>('system')
const isDark = ref(false)

function getSystemPreference(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function applyTheme() {
  if (theme.value === 'system') {
    isDark.value = getSystemPreference()
  } else {
    isDark.value = theme.value === 'dark'
  }

  if (isDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

function setTheme(newTheme: Theme) {
  theme.value = newTheme
  localStorage.setItem(STORAGE_KEY, newTheme)
  applyTheme()
}

function cycleTheme() {
  const order: Theme[] = ['system', 'light', 'dark']
  const currentIndex = order.indexOf(theme.value)
  const nextIndex = (currentIndex + 1) % order.length
  setTheme(order[nextIndex])
}

export function useTheme() {
  onMounted(() => {
    // localStorage から復元
    const stored = localStorage.getItem(STORAGE_KEY) as Theme | null
    if (stored && ['light', 'dark', 'system'].includes(stored)) {
      theme.value = stored
    }
    applyTheme()

    // OS 設定の変更を監視
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (theme.value === 'system') {
        applyTheme()
      }
    })
  })

  watchEffect(() => {
    applyTheme()
  })

  return { theme, isDark, setTheme, cycleTheme }
}
