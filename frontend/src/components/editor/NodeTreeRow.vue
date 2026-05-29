<script setup lang="ts">
import { computed } from 'vue'
import type { TreeRow } from '@/utils/nodeTree'

// 单个节点行（B3a-2）。仅展示 + 派发意图。chip command：l0(正文)/l1/l2/l3/step/node。
interface Props {
  row: TreeRow
  selected: boolean
  selectedForMark: boolean
  indeterminate?: boolean
  dropHint: '' | 'before' | 'after'
  readonly?: boolean
}
const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'select'): void
  (e: 'toggle'): void
  (e: 'check', shift: boolean): void
  (e: 'chip', command: string): void
  (e: 'remove'): void
  (e: 'dragstart', ev: DragEvent): void
  (e: 'dragover', ev: DragEvent): void
  (e: 'drop', ev: DragEvent): void
  (e: 'dragend'): void
  (e: 'indent', dir: 'in' | 'out'): void
}>()

const n = computed(() => props.row.node)
const levelLabel = computed(() => {
  const h = n.value.heading_level
  const base = h === null ? '正文' : `L${h}`
  return n.value.kind === 'step' ? `${base}·步骤` : base
})

function onCheck(ev: MouseEvent): void {
  emit('check', ev.shiftKey)
}

function onKeydown(ev: KeyboardEvent): void {
  if (props.readonly || ev.key !== 'Tab') return
  if (ev.target !== ev.currentTarget) return // 仅行本身聚焦（非内部 checkbox/chip）才缩进
  ev.preventDefault()
  emit('indent', ev.shiftKey ? 'out' : 'in')
}
</script>

<template>
  <div
    class="ntr"
    :class="[{ 'ntr--selected': selected }, dropHint ? `ntr--drop-${dropHint}` : '']"
    :style="{ boxSizing: 'border-box', paddingLeft: `${n.depth * 16 + 6}px` }"
    :draggable="!readonly"
    :tabindex="readonly ? undefined : -1"
    @click="emit('select')"
    @keydown="onKeydown"
    @dragstart="emit('dragstart', $event)"
    @dragover.prevent="emit('dragover', $event)"
    @drop.prevent="emit('drop', $event)"
    @dragend="emit('dragend')"
  >
    <span class="ntr-caret" :class="{ 'ntr-caret--hidden': !row.hasChildren }" @click.stop="emit('toggle')">
      {{ row.expanded ? '▾' : '▸' }}
    </span>
    <el-checkbox
      v-if="!readonly"
      :model-value="selectedForMark"
      :indeterminate="indeterminate"
      class="ntr-check"
      @click.stop="onCheck"
    />
    <span v-if="!readonly" class="ntr-actions" @click.stop>
      <el-dropdown trigger="click" :persistent="false" @command="(c: string) => emit('chip', c)">
        <el-button size="small" text class="ntr-chip">{{ levelLabel }} ▾</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="l0">正文</el-dropdown-item>
            <el-dropdown-item command="l1">一级章节</el-dropdown-item>
            <el-dropdown-item command="l2">二级章节</el-dropdown-item>
            <el-dropdown-item command="l3">三级章节</el-dropdown-item>
            <el-dropdown-item command="step" divided>设为步骤</el-dropdown-item>
            <el-dropdown-item command="node">取消步骤</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </span>
    <span class="ntr-code">{{ n.code }}</span>
    <span class="ntr-title">{{ row.title }}</span>
    <span v-if="n.mark_status === 'review'" class="ntr-review" title="解析存疑，待确认">待确认</span>
    <el-button v-if="!readonly" class="ntr-del" size="small" text title="删除" @click.stop="emit('remove')">✕</el-button>
  </div>
</template>

<style scoped>
.ntr { display: flex; align-items: center; gap: 4px; height: 30px; font-size: 13px; cursor: pointer; padding-right: 6px; white-space: nowrap; border-bottom: 1px solid transparent; }
.ntr:hover { background: var(--el-fill-color-light, #f5f7fa); }
.ntr--selected { background: var(--el-color-primary-light-9, #fbf1ee); }
.ntr--drop-before { box-shadow: inset 0 2px 0 var(--el-color-primary, #d97757); }
.ntr--drop-after { box-shadow: inset 0 -2px 0 var(--el-color-primary, #d97757); }
.ntr-caret { width: 14px; text-align: center; color: #999; flex: none; }
.ntr-caret--hidden { visibility: hidden; }
.ntr-check { flex: none; }
.ntr-actions { flex: none; }
.ntr-chip { font-variant-numeric: tabular-nums; }
.ntr-code { color: #888; font-variant-numeric: tabular-nums; flex: none; }
.ntr-title { overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }
.ntr-review { flex: none; font-size: 11px; line-height: 1; padding: 1px 4px; border-radius: 3px; color: #b88230; background: #fdf6ec; border: 1px solid #f5dab1; }
.ntr-del { flex: none; display: none; }
.ntr:hover .ntr-del { display: inline-flex; }
</style>
