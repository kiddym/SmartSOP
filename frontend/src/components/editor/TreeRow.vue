<script setup lang="ts">
import { computed } from 'vue'
import { FORM_TYPE_META } from '@/utils/editor'
import type { AddButtonState, FlatRow } from '@/types/node'

// 单个树行（§2.1 信息密度）。仅负责展示 + 派发意图，store 调用在 ChapterTreePanel。
interface Props {
  row: FlatRow
  selected: boolean
  markMode: boolean
  selectedForMark: boolean
  addState: AddButtonState
  editable: boolean
  canMoveUp: boolean
  canMoveDown: boolean
  canPromote: boolean
  canDemote: boolean
  dropHint: '' | 'before' | 'after' | 'inside' | 'invalid'
}
const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'select'): void
  (e: 'toggle'): void
  (e: 'add', kind: 'chapter' | 'content' | 'step'): void
  (e: 'move', dir: 'up' | 'down'): void
  (e: 'promote'): void
  (e: 'demote'): void
  (e: 'remove'): void
  (e: 'check', shift: boolean): void
  (e: 'dragstart', ev: DragEvent): void
  (e: 'dragover', ev: DragEvent): void
  (e: 'drop', ev: DragEvent): void
  (e: 'dragend'): void
}>()

const icon = computed(() => (props.row.kind === 'step' ? '☐' : props.row.kind === 'content' ? '📄' : '📘'))

// 图标颜色随 mark_status 表达「应用后会变成什么」（Q41）。
const colorClass = computed(() => {
  if (props.row.kind === 'step') return 'c-step'
  const m = props.row.mark_status
  if (m === 'step') return 'c-step'
  if (m === 'review') return 'c-review'
  if (props.row.kind === 'content' || m === 'content') return 'c-content'
  return 'c-chapter'
})

const display = computed(() => (props.row.title.trim() ? props.row.title : props.row.fallback))
const titleFallback = computed(() => !props.row.title.trim())
const typeColor = computed(() =>
  props.row.kind === 'step' && props.row.form_type ? FORM_TYPE_META[props.row.form_type].color : '',
)
const typeLabel = computed(() =>
  props.row.kind === 'step' && props.row.form_type ? FORM_TYPE_META[props.row.form_type].label : '',
)
</script>

<template>
  <div
    class="tr"
    :class="[{ 'tr--selected': selected }, dropHint ? `tr--drop-${dropHint}` : '']"
    :style="{ boxSizing: 'border-box', paddingLeft: `${row.depth * 16 + 6}px` }"
    :draggable="editable && !markMode"
    @click="emit('select')"
    @dragstart="emit('dragstart', $event)"
    @dragover.prevent="emit('dragover', $event)"
    @drop.prevent="emit('drop', $event)"
    @dragend="emit('dragend')"
  >
    <span
      class="tr-caret"
      :class="{ 'tr-caret--hidden': !row.has_children }"
      @click.stop="emit('toggle')"
    >
      {{ row.expanded ? '▾' : '▸' }}
    </span>

    <el-checkbox
      v-if="markMode && row.kind !== 'step'"
      :model-value="selectedForMark"
      class="tr-check"
      @click.stop="emit('check', ($event as MouseEvent).shiftKey)"
    />

    <span class="tr-icon" :class="colorClass">{{ icon }}</span>
    <span class="tr-code" :class="{ 'tr-code--skip': row.code === '#' }">{{ row.code }}</span>
    <span class="tr-title" :class="{ 'tr-title--fallback': titleFallback }">{{ display }}</span>

    <span v-if="row.mark_status === 'review'" class="tr-review" title="解析存疑，待确认">待确认</span>
    <span v-if="typeColor" class="tr-typebar" :class="`bar-${typeColor}`" :title="typeLabel">▮</span>
    <span v-if="row.require_confirmation" class="tr-flag" title="需操作员确认">⚠</span>

    <span v-if="editable && !markMode" class="tr-actions" @click.stop>
      <el-button
        v-if="addState.canAddChapter && row.kind === 'chapter'"
        size="small"
        text
        title="新增子章节"
        @click="emit('add', 'chapter')"
      >
        +章
      </el-button>
      <el-button
        v-if="addState.canAddContent && row.kind === 'chapter'"
        size="small"
        text
        title="新增内容块"
        @click="emit('add', 'content')"
      >
        +容
      </el-button>
      <el-button
        v-if="addState.canAddStep && row.kind === 'chapter'"
        size="small"
        text
        title="新增步骤"
        @click="emit('add', 'step')"
      >
        +步
      </el-button>
      <el-button
        v-if="row.kind === 'chapter' || row.kind === 'content'"
        size="small"
        text
        :disabled="!canPromote"
        title="提升层级（Shift+Tab）"
        @click="emit('promote')"
      >⇤</el-button>
      <el-button
        v-if="row.kind === 'chapter' || row.kind === 'content'"
        size="small"
        text
        :disabled="!canDemote"
        title="降低层级（Tab）"
        @click="emit('demote')"
      >⇥</el-button>
      <el-button size="small" text :disabled="!canMoveUp" title="上移" @click="emit('move', 'up')">
        ↑
      </el-button>
      <el-button
        size="small"
        text
        :disabled="!canMoveDown"
        title="下移"
        @click="emit('move', 'down')"
      >
        ↓
      </el-button>
      <el-button size="small" text title="删除" @click="emit('remove')">✕</el-button>
    </span>
  </div>
</template>

<style scoped>
.tr {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 30px;
  font-size: 13px;
  cursor: pointer;
  padding-right: 6px;
  border-bottom: 1px solid transparent;
  white-space: nowrap;
}
.tr:hover {
  background: var(--el-fill-color-light, #f5f7fa);
}
.tr--selected {
  background: var(--el-color-primary-light-9, #fbf1ee);
}
.tr--drop-before {
  box-shadow: inset 0 2px 0 var(--el-color-primary, #d97757);
}
.tr--drop-after {
  box-shadow: inset 0 -2px 0 var(--el-color-primary, #d97757);
}
.tr--drop-inside {
  background: var(--el-color-primary-light-8, #f7e4dd);
}
.tr--drop-invalid {
  box-shadow: inset 0 0 0 1px var(--el-color-danger, #f56c6c);
  cursor: not-allowed;
}
.tr-caret {
  width: 14px;
  text-align: center;
  color: #999;
  flex: none;
}
.tr-caret--hidden {
  visibility: hidden;
}
.tr-check {
  flex: none;
}
.tr-icon {
  flex: none;
}
.c-chapter {
  color: var(--el-color-primary, #d97757);
}
.c-step {
  color: #67c23a;
}
.c-content {
  color: #909399;
}
.c-review {
  color: #e6a23c;
}
.tr-code {
  color: #888;
  font-variant-numeric: tabular-nums;
  flex: none;
}
.tr-code--skip {
  color: #c0c4cc;
}
.tr-title {
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}
.tr-title--fallback {
  color: #aaa;
  font-style: italic;
}
.tr-typebar {
  flex: none;
}
.bar-gray {
  color: #909399;
}
.bar-blue {
  color: var(--el-color-primary, #d97757);
}
.bar-purple {
  color: #8e44ad;
}
.bar-cyan {
  color: #17a2b8;
}
.bar-orange {
  color: #e6a23c;
}
.bar-red {
  color: #f56c6c;
}
.tr-flag {
  color: #e6a23c;
  flex: none;
}
.tr-review {
  flex: none;
  font-size: 11px;
  line-height: 1;
  padding: 1px 4px;
  border-radius: 3px;
  color: #b88230;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
}
.tr-actions {
  display: none;
  flex: none;
}
.tr:hover .tr-actions {
  display: inline-flex;
}
</style>
