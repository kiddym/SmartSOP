// 编辑器全局键盘快捷键（§17.9 / Q164）。输入框 / WangEditor focus 时降级，避免冲突。
import { onBeforeUnmount, onMounted } from 'vue'

interface Handlers {
  onSave: () => void
  onUndo: () => void
  onRedo: () => void
  onFocusSearch: () => void
  onDelete: () => void
  onEsc: () => void
}

function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el) return false
  return el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable
}

export function useEditorKeyboard(h: Handlers): void {
  function handler(e: KeyboardEvent): void {
    const mod = e.ctrlKey || e.metaKey
    const k = e.key.toLowerCase()
    if (mod && k === 's') {
      e.preventDefault()
      h.onSave()
      return
    }
    if (mod && e.shiftKey && k === 'z') {
      if (!isTyping(e.target)) {
        e.preventDefault()
        h.onRedo()
      }
      return
    }
    if (mod && k === 'z') {
      if (!isTyping(e.target)) {
        e.preventDefault()
        h.onUndo()
      }
      return
    }
    if (e.key === '/' && !isTyping(e.target)) {
      e.preventDefault()
      h.onFocusSearch()
      return
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && !isTyping(e.target)) {
      h.onDelete()
      return
    }
    if (e.key === 'Escape') h.onEsc()
  }

  onMounted(() => window.addEventListener('keydown', handler))
  onBeforeUnmount(() => window.removeEventListener('keydown', handler))
}
