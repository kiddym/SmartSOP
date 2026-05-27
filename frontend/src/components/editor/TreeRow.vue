<script setup lang="ts">
import { computed } from 'vue'
import { FORM_TYPE_META, TITLE_TOOLTIP_THRESHOLD } from '@/utils/editor'
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
  dropHint: '' | 'before' | 'after' | 'inside' | 'invalid'
  indeterminate?: boolean
}
const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'select'): void
  (e: 'toggle'): void
  (e: 'add', kind: 'chapter' | 'content' | 'step'): void
  (e: 'move', dir: 'up' | 'down'): void
  (e: 'remove'): void
  (e: 'convert', dir: 'to-step' | 'to-content' | 'chapter-to-content'): void
  (e: 'check', shift: boolean): void
  (e: 'dragstart', ev: DragEvent): void
  (e: 'dragover', ev: DragEvent): void
  (e: 'drop', ev: DragEvent): void
  (e: 'dragend'): void
}>()

function onMore(c: 'to-step' | 'to-content' | 'chapter-to-content' | 'remove'): void {
  if (c === 'remove') emit('remove')
  else emit('convert', c)
}

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
const missingTitle = computed(() => props.row.kind === 'chapter' && !props.row.title.trim())
const typeColor = computed(() =>
  props.row.kind === 'step' && props.row.form_type ? FORM_TYPE_META[props.row.form_type].color : '',
)
const typeLabel = computed(() =>
  props.row.kind === 'step' && props.row.form_type ? FORM_TYPE_META[props.row.form_type].label : '',
)

const tooltipDisabled = computed(
  () => props.row.kind !== 'chapter' || display.value.length <= TITLE_TOOLTIP_THRESHOLD
)
</script>

<template>
  <div
    class="tr"
    :class="[{ 'tr--selected': selected, 'tr--missing': missingTitle }, dropHint ? `tr--drop-${dropHint}` : '']"
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
      v-if="markMode"
      :model-value="selectedForMark"
      :indeterminate="row.kind === 'chapter' ? !!indeterminate : false"
      class="tr-check"
      @click.stop="emit('check', ($event as MouseEvent).shiftKey)"
    />

    <span class="tr-icon" :class="colorClass">{{ icon }}</span>
    <span class="tr-code" :class="{ 'tr-code--skip': row.code === '#' }">{{ row.code }}</span>
    <el-tooltip
      :content="display"
      :disabled="tooltipDisabled"
      placement="top-start"
      :show-after="300"
      popper-class="tr-title-tooltip"
    >
      <span class="tr-title" :class="{ 'tr-title--fallback': titleFallback }">{{ display }}</span>
    </el-tooltip>

    <span v-if="row.mark_status === 'review'" class="tr-review" title="解析存疑，待确认">待确认</span>
    <span v-if="typeColor" class="tr-typebar" :class="`bar-${typeColor}`" :title="typeLabel">▮</span>

    <span v-if="missingTitle" class="tr-missing-tag" title="章节标题为空">缺标题</span>

    <span v-if="editable && !markMode" class="tr-actions" @click.stop>
      <el-dropdown
        v-if="addState.canAddChapter || addState.canAddContent || addState.canAddStep"
        trigger="click"
        :persistent="false"
        @command="(c: 'chapter' | 'content' | 'step') => emit('add', c)"
      >
        <el-button size="small" text class="add-trigger">＋新增 ▾</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item :disabled="!addState.canAddChapter" command="chapter">子章节</el-dropdown-item>
            <el-dropdown-item :disabled="!addState.canAddContent" command="content">内容块</el-dropdown-item>
            <el-dropdown-item :disabled="!addState.canAddStep" command="step">步骤</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button size="small" text :disabled="!canMoveUp" title="上移" @click="emit('move', 'up')">↑</el-button>
      <el-button size="small" text :disabled="!canMoveDown" title="下移" @click="emit('move', 'down')">↓</el-button>
      <el-dropdown trigger="click" :persistent="false" @command="onMore">
        <el-button size="small" text class="more-trigger" title="更多">⋮</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-if="row.kind === 'content'" command="to-step">转为步骤</el-dropdown-item>
            <el-dropdown-item v-if="row.kind === 'step'" command="to-content">转为内容块</el-dropdown-item>
            <el-dropdown-item
              v-if="row.kind === 'chapter'"
              command="chapter-to-content"
              :disabled="row.has_children"
            >
              转为内容块
            </el-dropdown-item>
            <el-dropdown-item command="remove" divided>删除</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
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
.tr--missing {
  box-shadow: inset 3px 0 0 var(--el-color-warning, #e6a23c);
  background: #fffaf2;
}
.tr-missing-tag {
  flex: none;
  font-size: 11px;
  line-height: 1;
  padding: 1px 5px;
  border-radius: 3px;
  color: #b88230;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
}
.tr-actions .el-dropdown {
  height: 100%;
  display: inline-flex;
  align-items: center;
}
</style>

<style>
.tr-title-tooltip {
  max-width: 400px;
  white-space: normal;
  word-break: break-word;
}
</style>
