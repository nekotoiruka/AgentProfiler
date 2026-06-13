/**
 * DiscussionTheater.vue ユニットテスト
 * Validates: Requirements 22.3, 22.4, 22.5, 22.6
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DiscussionTheater from './DiscussionTheater.vue'
import type { DiscussionTurn } from './composables/useDiscussion'

function createTurns(count: number): DiscussionTurn[] {
  const agents = ['agent_1', 'agent_2', 'agent_3']
  const names = ['アリス', 'ボブ', 'キャロル']
  return Array.from({ length: count }, (_, i) => ({
    discussion_id: 'disc_001',
    turn_number: i + 1,
    agent_id: agents[i % agents.length],
    display_name: names[i % names.length],
    content: `ターン ${i + 1} のメッセージ`,
    timestamp: `2024-01-01T00:0${i}:00Z`,
  }))
}

describe('DiscussionTheater', () => {
  it('ターンカウンターに現在ターン数と合計を表示する', () => {
    const wrapper = mount(DiscussionTheater, {
      props: {
        turns: createTurns(3),
        streaming: false,
        progress: 30,
        totalExpectedTurns: 10,
      },
    })

    expect(wrapper.find('.turn-counter').text()).toBe('3 / 10 ターン')
  })

  it('プログレスバーの幅が progress に連動する', () => {
    const wrapper = mount(DiscussionTheater, {
      props: {
        turns: createTurns(5),
        streaming: false,
        progress: 50,
        totalExpectedTurns: 10,
      },
    })

    const fill = wrapper.find('.progress-fill')
    expect(fill.attributes('style')).toContain('width: 50%')
  })

  it('streaming 時に LIVE バッジを表示する', () => {
    const wrapper = mount(DiscussionTheater, {
      props: {
        turns: createTurns(1),
        streaming: true,
        progress: 10,
        totalExpectedTurns: 10,
      },
    })

    expect(wrapper.find('.live-badge').exists()).toBe(true)
    expect(wrapper.find('.live-badge').text()).toContain('LIVE')
  })

  it('streaming でない場合は LIVE バッジを非表示にする', () => {
    const wrapper = mount(DiscussionTheater, {
      props: {
        turns: createTurns(1),
        streaming: false,
        progress: 100,
        totalExpectedTurns: 10,
      },
    })

    expect(wrapper.find('.live-badge').exists()).toBe(false)
  })

  it('ターンごとに TurnBubble コンポーネントをレンダリングする', () => {
    const wrapper = mount(DiscussionTheater, {
      props: {
        turns: createTurns(4),
        streaming: false,
        progress: 40,
        totalExpectedTurns: 10,
      },
    })

    const bubbles = wrapper.findAll('.turn-bubble')
    expect(bubbles).toHaveLength(4)
  })

  it('ターンが空の場合に空状態メッセージを表示する', () => {
    const wrapper = mount(DiscussionTheater, {
      props: {
        turns: [],
        streaming: false,
        progress: 0,
        totalExpectedTurns: 10,
      },
    })

    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.find('.empty-state').text()).toContain('議論を開始すると')
  })

  it('Playback モード切替ボタンが動作する', async () => {
    const wrapper = mount(DiscussionTheater, {
      props: {
        turns: createTurns(2),
        streaming: true,
        progress: 20,
        totalExpectedTurns: 10,
      },
    })

    const btn = wrapper.find('.mode-toggle')
    expect(btn.text()).toContain('リアルタイム')

    await btn.trigger('click')
    expect(btn.text()).toContain('シミュレーション')
    expect(btn.classes()).toContain('active')

    await btn.trigger('click')
    expect(btn.text()).toContain('リアルタイム')
    expect(btn.classes()).not.toContain('active')
  })

  it('progressbar に aria 属性が設定されている', () => {
    const wrapper = mount(DiscussionTheater, {
      props: {
        turns: createTurns(3),
        streaming: false,
        progress: 75,
        totalExpectedTurns: 10,
      },
    })

    const bar = wrapper.find('.progress-bar')
    expect(bar.attributes('role')).toBe('progressbar')
    expect(bar.attributes('aria-valuenow')).toBe('75')
    expect(bar.attributes('aria-valuemin')).toBe('0')
    expect(bar.attributes('aria-valuemax')).toBe('100')
  })
})
