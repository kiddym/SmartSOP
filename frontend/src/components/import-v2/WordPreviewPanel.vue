<script setup lang="ts">
import { ref, watchEffect } from 'vue'
import { renderAsync } from 'docx-preview'

const props = defineProps<{ file: File | null }>()

const docxRef = ref<HTMLDivElement | null>(null)
const renderError = ref(false)
const zoomLevel = ref(1.0)
const isPanMode = ref(false)
const scrollAreaRef = ref<HTMLDivElement | null>(null)
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 })

function zoomOut() { zoomLevel.value = Math.max(0.3, parseFloat((zoomLevel.value - 0.2).toFixed(1))) }
function zoomIn() { zoomLevel.value = Math.min(2.0, parseFloat((zoomLevel.value + 0.2).toFixed(1))) }
function resetZoom() { zoomLevel.value = 1.0 }
function togglePanMode() { isPanMode.value = !isPanMode.value }

function onPanMouseDown(e: MouseEvent) {
  if (!isPanMode.value || !scrollAreaRef.value) return
  isPanning.value = true
  panStart.value = {
    x: e.clientX, y: e.clientY,
    scrollLeft: scrollAreaRef.value.scrollLeft,
    scrollTop: scrollAreaRef.value.scrollTop,
  }
}
function onPanMouseMove(e: MouseEvent) {
  if (!isPanning.value || !scrollAreaRef.value) return
  e.preventDefault()
  scrollAreaRef.value.scrollLeft = panStart.value.scrollLeft - (e.clientX - panStart.value.x)
  scrollAreaRef.value.scrollTop = panStart.value.scrollTop - (e.clientY - panStart.value.y)
}
function onPanMouseUp() { isPanning.value = false }

watchEffect(async () => {
  const el = docxRef.value
  const file = props.file
  if (!el || !file) return
  renderError.value = false
  el.innerHTML = ''
  try {
    await renderAsync(file, el, undefined, { className: 'docx-render', ignoreWidth: true })
  } catch {
    renderError.value = true
  }
})
</script>

<template>
  <div class="word-preview">
    <div class="head">
      <span>Word 原文预览</span>
      <div class="controls">
        <el-button text size="small" @click="zoomOut">－</el-button>
        <span class="zoom" @click="resetZoom">{{ Math.round(zoomLevel * 100) }}%</span>
        <el-button text size="small" @click="zoomIn">＋</el-button>
        <el-button text size="small" :type="isPanMode ? 'primary' : ''" @click="togglePanMode">🖐</el-button>
      </div>
    </div>
    <div v-if="!file" class="empty"><el-empty description="未加载文档" /></div>
    <div v-else-if="renderError" class="empty"><el-empty description="预览加载失败" /></div>
    <div
      v-else
      ref="scrollAreaRef"
      class="scroll"
      :class="{ 'pan-mode': isPanMode, panning: isPanning }"
      @mousedown="onPanMouseDown"
      @mousemove="onPanMouseMove"
      @mouseup="onPanMouseUp"
      @mouseleave="onPanMouseUp"
    >
      <div ref="docxRef" class="docx" :style="{ zoom: zoomLevel }" />
    </div>
  </div>
</template>

<style scoped>
.word-preview { display: flex; flex-direction: column; height: 100%; border-right: 1px solid var(--el-border-color-lighter, #ebeef5); }
.head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 6px 12px; font-size: 13px; font-weight: 600;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.controls { display: flex; align-items: center; gap: 2px; }
.zoom { font-size: 12px; color: #606266; min-width: 36px; text-align: center; cursor: pointer; }
.zoom:hover { color: #409eff; }
.empty { flex: 1; display: flex; align-items: center; justify-content: center; }
.scroll { flex: 1; overflow: auto; padding: 0 8px 8px; }
.scroll.pan-mode { cursor: grab; }
.scroll.pan-mode.panning { cursor: grabbing; user-select: none; }
:deep(.docx-render) { font-size: 13px; }
:deep(.docx-render img) { max-width: 100%; }
</style>
