import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'

import { useBatchReviewShortcuts } from '@/composables/useBatchReviewShortcuts'

function makeHandlers() {
  return {
    onPrev: vi.fn(),
    onNext: vi.fn(),
    onOpen: vi.fn(),
    onApply: vi.fn(),
    onSkip: vi.fn(),
  }
}

function setup(handlers: ReturnType<typeof makeHandlers>) {
  const Comp = defineComponent({
    setup() {
      useBatchReviewShortcuts(handlers)
      return () => h('div')
    },
  })
  return mount(Comp, { attachTo: document.body })
}

describe('useBatchReviewShortcuts', () => {
  it('maps keys to handlers (j/k/Enter/a/s)', () => {
    const handlers = makeHandlers()
    const w = setup(handlers)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'j' }))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k' }))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 's' }))
    expect(handlers.onNext).toHaveBeenCalledTimes(1)
    expect(handlers.onPrev).toHaveBeenCalledTimes(1)
    expect(handlers.onOpen).toHaveBeenCalledTimes(1)
    expect(handlers.onApply).toHaveBeenCalledTimes(1)
    expect(handlers.onSkip).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('ignores shortcuts when focus is in an editable element', () => {
    const handlers = makeHandlers()
    const w = setup(handlers)
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'j', bubbles: true }))
    expect(handlers.onNext).not.toHaveBeenCalled()
    input.remove()
    w.unmount()
  })

  it('removes the listener on unmount (no leak)', () => {
    const handlers = makeHandlers()
    const w = setup(handlers)
    w.unmount()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'j' }))
    expect(handlers.onNext).not.toHaveBeenCalled()
  })
})
