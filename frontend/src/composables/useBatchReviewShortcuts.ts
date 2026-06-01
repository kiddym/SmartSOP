import { onMounted, onUnmounted } from 'vue'

interface Handlers {
  onPrev: () => void
  onNext: () => void
  onOpen: () => void
  onApply: () => void
  onSkip: () => void
}

function inEditable(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null
  if (!node) return false
  const tag = node.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || node.isContentEditable
}

export function useBatchReviewShortcuts(h: Handlers): void {
  function onKey(e: KeyboardEvent): void {
    if (inEditable(e.target)) return
    switch (e.key) {
      case 'ArrowUp':
      // falls through
      case 'k':
        e.preventDefault()
        h.onPrev()
        break
      case 'ArrowDown':
      // falls through
      case 'j':
        e.preventDefault()
        h.onNext()
        break
      case 'Enter':
        e.preventDefault()
        h.onOpen()
        break
      case 'a':
      // falls through
      case 'A':
        e.preventDefault()
        h.onApply()
        break
      case 's':
      // falls through
      case 'S':
        e.preventDefault()
        h.onSkip()
        break
    }
  }
  onMounted(() => window.addEventListener('keydown', onKey))
  onUnmounted(() => window.removeEventListener('keydown', onKey))
}
