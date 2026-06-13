/**
 * TurnBubble.vue ユニットテスト
 * Validates: Requirements 22.3
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TurnBubble from './TurnBubble.vue'
import type { DiscussionTurn } from './composables/useDiscussion'

function createTurn(overrides: Partial<DiscussionTurn> = {}): DiscussionTurn {
  return {
    discussion_id: 'disc_001',
    turn_number: 1,
    agent_id: 'agent_1',
    display_name: 'アリス',
    content: 'テストメッセージです',
    timestamp: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('TurnBubble', () => {
  it('display_name の先頭文字をアバターに表示する', () => {
    const wrapper = mount(TurnBubble, {
      props: { turn: createTurn({ display_name: 'ボブ' }), colorIndex: 0 },
    })

    expect(wrapper.find('.avatar').text()).toBe('ボ')
  })

  it('display_name とターン番号を表示する', () => {
    const wrapper = mount(TurnBubble, {
      props: { turn: createTurn({ display_name: 'アリス', turn_number: 3 }), colorIndex: 0 },
    })

    expect(wrapper.find('.name').text()).toBe('アリス')
    expect(wrapper.find('.turn-number').text()).toBe('Turn 3')
  })

  it('コンテンツを表示する', () => {
    const wrapper = mount(TurnBubble, {
      props: { turn: createTurn({ content: 'こんにちは世界' }), colorIndex: 0 },
    })

    expect(wrapper.find('.text').text()).toBe('こんにちは世界')
  })

  it('colorIndex に基づいたカラーをアバターに適用する', () => {
    const wrapper = mount(TurnBubble, {
      props: { turn: createTurn(), colorIndex: 1 },
    })

    const avatar = wrapper.find('.avatar')
    expect(avatar.attributes('style')).toContain('background-color: rgb(239, 68, 68)')
  })

  it('colorIndex が6以上の場合は循環して色を適用する', () => {
    const wrapper = mount(TurnBubble, {
      props: { turn: createTurn(), colorIndex: 6 },
    })

    // colorIndex 6 → 6 % 6 = 0 → '#3b82f6'
    const avatar = wrapper.find('.avatar')
    expect(avatar.attributes('style')).toContain('background-color: rgb(59, 130, 246)')
  })

  it('アバターに aria-label が設定されている', () => {
    const wrapper = mount(TurnBubble, {
      props: { turn: createTurn({ display_name: 'テスト' }), colorIndex: 0 },
    })

    expect(wrapper.find('.avatar').attributes('aria-label')).toBe('テスト のアバター')
  })
})
