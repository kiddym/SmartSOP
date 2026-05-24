<script setup lang="ts">
import { computed, ref, watchEffect } from 'vue'
import { renderAsync } from 'docx-preview'
import {
  applyBatchMark,
  validateMarkedBlocks,
  type MarkRole,
  type MarkedImportBlock,
} from '@/utils/importBlocks'

const props = defineProps<{ modelValue: MarkedImportBlock[]; file?: File | null }>()
const emit = defineEmits<{ (e: 'update:modelValue', blocks: MarkedImportBlock[]): void }>()

const selected = ref<string[]>([])
const docxRef = ref<HTMLDivElement | null>(null)
const renderError = ref(false)

// Zoom & pan controls
const zoomLevel = ref(1.0)
const isPanMode = ref(false)
const scrollAreaRef = ref<HTMLDivElement | null>(null)
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 })

function zoomOut() {
  zoomLevel.value = Math.max(0.3, parseFloat((zoomLevel.value - 0.2).toFixed(1)))
}
function zoomIn() {
  zoomLevel.value = Math.min(2.0, parseFloat((zoomLevel.value + 0.2).toFixed(1)))
}
function resetZoom() {
  zoomLevel.value = 1.0
}
function togglePanMode() {
  isPanMode.value = !isPanMode.value
}
function onPanMouseDown(e: MouseEvent) {
  if (!isPanMode.value || !scrollAreaRef.value) return
  isPanning.value = true
  panStart.value = {
    x: e.clientX,
    y: e.clientY,
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
function onPanMouseUp() {
  isPanning.value = false
}

const issues = computed(() => validateMarkedBlocks(props.modelValue))
const selectedCount = computed(() => selected.value.length)

// Compute visual depth for each block so the flat list looks like a tree
const depthMap = computed(() => {
  const map: Record<string, number> = {}
  let currentDepth = 0
  for (const block of props.modelValue) {
    if (block.assigned_role === 'chapter_1') {
      currentDepth = 0
      map[block.id] = 0
    } else if (block.assigned_role === 'chapter_2') {
      currentDepth = 1
      map[block.id] = 1
    } else if (block.assigned_role === 'chapter_3') {
      currentDepth = 2
      map[block.id] = 2
    } else if (block.assigned_role === 'content') {
      map[block.id] = currentDepth + 1
    } else {
      map[block.id] = 0
    }
  }
  return map
})

// Compute hierarchical numbering for chapter blocks
const numberingMap = computed(() => {
  const map: Record<string, string> = {}
  let c1 = 0, c2 = 0, c3 = 0
  for (const block of props.modelValue) {
    if (block.assigned_role === 'chapter_1') {
      c1++; c2 = 0; c3 = 0
      map[block.id] = `${c1}`
    } else if (block.assigned_role === 'chapter_2') {
      c2++; c3 = 0
      map[block.id] = `${c1}.${c2}`
    } else if (block.assigned_role === 'chapter_3') {
      c3++
      map[block.id] = `${c1}.${c2}.${c3}`
    }
  }
  return map
})

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

function checked(id: string): boolean {
  return selected.value.includes(id)
}

function setChecked(id: string, value: boolean): void {
  selected.value = value ? [...new Set([...selected.value, id])] : selected.value.filter((x) => x !== id)
}

function mark(role: MarkRole): void {
  if (!selected.value.length) return
  emit('update:modelValue', applyBatchMark(props.modelValue, selected.value, role))
}

function clearSelection(): void {
  selected.value = []
}

function roleText(role: MarkRole): string {
  if (role === 'chapter_1') return '一级'
  if (role === 'chapter_2') return '二级'
  if (role === 'chapter_3') return '三级'
  if (role === 'ignored') return '忽略'
  return '正文'
}

function roleTagType(role: MarkRole): '' | 'primary' | 'info' {
  if (role === 'chapter_1' || role === 'chapter_2' || role === 'chapter_3') return 'primary'
  if (role === 'ignored') return 'info'
  return ''
}

function issueFor(id: string): string {
  return issues.value.find((i) => i.block_id === id)?.message ?? ''
}
</script>

<template>
  <div class="marking-step">
    <div class="panes">
      <!-- Left: Word document preview -->
      <div class="docx-pane">
        <div class="pane-title">
          <span>Word 原文预览</span>
          <div class="docx-controls">
            <button class="ctrl-btn" title="缩小" @click="zoomOut">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zM7 9h5v1H7z"/></svg>
            </button>
            <span class="zoom-label" @click="resetZoom" title="点击重置">{{ Math.round(zoomLevel * 100) }}%</span>
            <button class="ctrl-btn" title="放大" @click="zoomIn">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zM13 10h-3v3H9v-3H6V9h3V6h1v3h3v1z"/></svg>
            </button>
            <button class="ctrl-btn pan-btn" :class="{ active: isPanMode }" title="手形拖拽模式" @click="togglePanMode">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M9 11.24V7.5C9 6.12 10.12 5 11.5 5S14 6.12 14 7.5v3.74c1.21-.81 2-2.18 2-3.74C16 5.01 13.99 3 11.5 3S7 5.01 7 7.5c0 1.56.79 2.93 2 3.74zm9.84 4.63l-4.54-2.26c-.17-.07-.35-.11-.54-.11H13v-6c0-.83-.67-1.5-1.5-1.5S10 6.67 10 7.5v10.74l-3.43-.72c-.08-.01-.15-.03-.24-.03-.31 0-.59.13-.79.33l-.79.8 4.94 4.94c.27.27.65.44 1.06.44h6.79c.75 0 1.33-.55 1.44-1.28l.75-5.27c.01-.07.02-.14.02-.2 0-.62-.38-1.16-.91-1.38z"/></svg>
            </button>
          </div>
        </div>
        <div v-if="!props.file" class="docx-empty">
          <el-empty description="未加载文档" />
        </div>
        <div v-else-if="renderError" class="docx-empty">
          <el-empty description="预览加载失败" />
        </div>
        <div
          v-show="props.file && !renderError"
          ref="scrollAreaRef"
          class="docx-scroll-area"
          :class="{ 'pan-mode': isPanMode, 'panning': isPanning }"
          @mousedown="onPanMouseDown"
          @mousemove="onPanMouseMove"
          @mouseup="onPanMouseUp"
          @mouseleave="onPanMouseUp"
        >
          <div ref="docxRef" class="docx-container" :style="{ zoom: zoomLevel }" />
        </div>
      </div>

      <!-- Right: toolbar + interactive block list (indented by role) -->
      <div class="right-pane">
        <div class="toolbar">
          <span class="hint">已选 {{ selectedCount }} 项</span>
          <span class="spacer" />
          <el-button size="small" @click="mark('chapter_1')">一级章节</el-button>
          <el-button size="small" @click="mark('chapter_2')">二级章节</el-button>
          <el-button size="small" @click="mark('chapter_3')">三级章节</el-button>
          <el-button size="small" @click="mark('content')">正文</el-button>
          <el-button size="small" @click="mark('ignored')">忽略</el-button>
          <el-button size="small" type="info" plain :disabled="!selectedCount" @click="clearSelection">取消选择</el-button>
        </div>

        <el-alert
          v-if="issues.some((i) => i.level === 'error')"
          class="banner"
          type="error"
          :closable="false"
          show-icon
          title="存在层级错误，请修正后再继续导入。"
        />
        <el-alert
          v-else-if="issues.some((i) => i.level === 'warning')"
          class="banner"
          type="warning"
          :closable="false"
          show-icon
          title="存在章节前正文，确认不需要导入时可标为忽略。"
        />

        <div class="blocks">
          <div
            v-for="block in modelValue"
            :key="block.id"
            class="block-row"
            :class="{ ignored: block.assigned_role === 'ignored', selected: checked(block.id) }"
            :style="{ paddingLeft: `${8 + (depthMap[block.id] ?? 0) * 18}px` }"
            @click="setChecked(block.id, !checked(block.id))"
          >
            <el-checkbox
              :model-value="checked(block.id)"
              @update:model-value="(v: boolean) => setChecked(block.id, v)"
              @click.stop
            />
            <el-tag size="small" :type="roleTagType(block.assigned_role)" disable-transitions>
              {{ roleText(block.assigned_role) }}
            </el-tag>
            <span v-if="numberingMap[block.id]" class="chapter-number">{{ numberingMap[block.id] }}</span>
            <span class="block-text">{{ block.display_text || '（空块）' }}</span>
            <el-tag v-if="block.has_word_numbering" size="small" type="info" disable-transitions>Word编号</el-tag>
            <el-tag v-if="block.mark_status === 'review'" size="small" type="warning" disable-transitions>待确认</el-tag>
            <span v-if="issueFor(block.id)" class="issue">{{ issueFor(block.id) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.marking-step {
  padding: 8px 0;
}
.panes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  height: 560px;
}
.docx-pane {
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.pane-title {
  padding: 6px 10px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
  background: #fff;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.docx-controls {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.ctrl-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  background: #fff;
  cursor: pointer;
  color: #606266;
  padding: 0;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.ctrl-btn:hover {
  background: #f0f2f5;
  border-color: #c0c4cc;
  color: #303133;
}
.ctrl-btn.active {
  background: #ecf5ff;
  border-color: #409eff;
  color: #409eff;
}
.zoom-label {
  font-size: 11px;
  color: #606266;
  min-width: 32px;
  text-align: center;
  cursor: pointer;
  user-select: none;
  padding: 0 2px;
}
.zoom-label:hover {
  color: #409eff;
}
.docx-scroll-area {
  flex: 1;
  overflow: auto;
  min-height: 0;
}
.docx-scroll-area.pan-mode {
  cursor: grab;
}
.docx-scroll-area.pan-mode.panning {
  cursor: grabbing;
  user-select: none;
}
.docx-container {
  padding: 0 8px 8px;
}
.docx-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
:deep(.docx-render) {
  font-size: 13px;
}
:deep(.docx-render img) {
  max-width: 100%;
}
.right-pane {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
  min-height: 0;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.hint {
  color: #606266;
  font-size: 13px;
}
.spacer {
  flex: 1;
}
.banner {
  flex-shrink: 0;
}
.blocks {
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
  overflow: auto;
  flex: 1;
  min-height: 0;
}
.block-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 6px 8px;
  border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0);
  cursor: pointer;
  transition: background 0.1s;
}
.block-row:hover {
  background: #f5f7fa;
}
.block-row.selected {
  background: #ecf5ff;
}
.block-row.ignored {
  color: #909399;
  background: #fafafa;
}
.block-row.ignored.selected {
  background: #e8f0fe;
}
.chapter-number {
  font-size: 12px;
  color: #409eff;
  font-weight: 600;
  flex-shrink: 0;
  min-width: 28px;
}
.block-text {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.issue {
  color: #f56c6c;
  font-size: 12px;
}
</style>
