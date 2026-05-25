<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useStorage, useEventListener } from '@vueuse/core'
import WordPreviewPanel from '@/components/import-v2/WordPreviewPanel.vue'
import ImportSideRail from '@/components/import-v2/ImportSideRail.vue'
import { fetchSourceDocx } from '@/api/procedures'
import {
  PREVIEW_DEFAULTS,
  resizePreview,
  sanitizePreview,
  type PreviewState,
} from '@/utils/editorPreview'

const props = defineProps<{ procedureId: string }>()

const DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const file = ref<File | null>(null)
const everShown = ref(false) // 渲染延迟：首次展开后才挂载 WordPreviewPanel

const state = useStorage<PreviewState>('smartsop.editor.preview', { ...PREVIEW_DEFAULTS })
state.value = sanitizePreview(state.value)

onMounted(async () => {
  const got = await fetchSourceDocx(props.procedureId)
  if (!got) return
  file.value = new File([got.blob], got.filename, { type: DOCX_MIME })
  if (!state.value.collapsed) everShown.value = true
})

watch(
  () => state.value.collapsed,
  (c) => { if (!c) everShown.value = true },
)

// 拖拽调宽
const drag = ref<{ startX: number; startW: number } | null>(null)
function onDragStart(e: PointerEvent): void {
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  drag.value = { startX: e.clientX, startW: state.value.width }
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
}
function endDrag(): void {
  if (!drag.value) return
  drag.value = null
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
}
useEventListener(window, 'pointermove', (e: PointerEvent) => {
  if (!drag.value) return
  state.value = resizePreview({ collapsed: false, width: drag.value.startW }, e.clientX - drag.value.startX)
})
useEventListener(window, 'pointerup', endDrag)
useEventListener(window, 'pointercancel', endDrag)
function resetWidth(): void {
  state.value = { collapsed: false, width: PREVIEW_DEFAULTS.width }
}
</script>

<template>
  <div
    v-if="file"
    class="preview-col"
    :style="{ width: (state.collapsed ? 32 : state.width) + 'px' }"
  >
    <ImportSideRail
      v-if="state.collapsed"
      label="Word 原文预览"
      side="left"
      @expand="state.collapsed = false"
    />
    <template v-else>
      <WordPreviewPanel v-if="everShown" :file="file" class="preview-body" />
      <div class="preview-splitter" title="拖拽调宽，双击重置" @pointerdown="onDragStart" @dblclick="resetWidth">
        <button class="collapse-btn" title="折叠原文预览" @click.stop="state.collapsed = true" @pointerdown.stop>«</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.preview-col {
  flex: none;
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.preview-body { flex: 1; min-height: 0; }
.preview-splitter {
  position: absolute;
  top: 0;
  right: -3px;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  z-index: 2;
  touch-action: none;
}
.collapse-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 18px;
  height: 36px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  background: #fff;
  color: #909399;
  font-size: 12px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, border-color 0.15s;
}
.preview-splitter:hover .collapse-btn { opacity: 1; }
.collapse-btn:hover { color: var(--el-color-primary, #d97757); border-color: var(--el-color-primary, #d97757); }
</style>
