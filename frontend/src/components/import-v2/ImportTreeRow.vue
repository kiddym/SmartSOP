<script setup lang="ts">
import { computed } from 'vue'
import type { WizardNode } from '@/utils/importTree'
import type { ImportDialogMode } from '@/composables/useImportDialog'

interface Props {
  node: WizardNode
  depth: number
  level: number
  number: string
  selected: boolean
  mode: ImportDialogMode
  checked: boolean
  canMoveUp?: boolean
  canMoveDown?: boolean
}
const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'select'): void
  (e: 'check', v: boolean): void
  (e: 'move', dir: -1 | 1): void
  (e: 'remove'): void
}>()

const LEVEL_LABEL = ['', '一级', '二级', '三级'] as const

const tagLabel = computed(() => {
  if (props.node.content_type === 'content') return '正文'
  return LEVEL_LABEL[Math.min(props.level, 3)] || ''
})

const tagType = computed<'primary' | 'info' | ''>(() => {
  if (props.node.content_type === 'content') return 'info'
  return 'primary'
})

const showHoverActions = computed(() => props.mode === 'normal')
const showCheckbox = computed(() => props.mode !== 'normal')
const stepBadge = computed(() => props.node.mark_status === 'step')
const contentBadge = computed(() => props.node.mark_status === 'content' && props.node.content_type !== 'content')
const reviewTag = computed(() => props.node.mark_status === 'review')

function snippetOf(html: string): string {
  if (typeof document === 'undefined') return html.replace(/<[^>]+>/g, '').trim().slice(0, 30)
  const el = document.createElement('div')
  el.innerHTML = html
  return (el.textContent ?? '').trim().slice(0, 30)
}
</script>

<template>
  <div
    class="tr"
    :class="{ 'tr--selected': selected }"
    :style="{ paddingLeft: `${depth * 16 + 8}px` }"
    @click="emit('select')"
  >
    <el-checkbox
      v-if="showCheckbox"
      :model-value="checked"
      class="tr-check"
      @click.stop
      @update:model-value="(v: boolean) => emit('check', v)"
    />
    <el-tag size="small" :type="tagType" disable-transitions class="tr-tag">{{ tagLabel }}</el-tag>
    <span v-if="number" class="tr-num">{{ number }}</span>
    <span class="tr-title" :class="{ 'tr-title--empty': !node.title && node.content_type === 'chapter' }">
      {{ node.title || (node.content_type === 'content' ? snippetOf(node.rich_content) : '（无标题）') }}
    </span>
    <el-tag v-if="stepBadge" size="small" type="warning" disable-transitions>→步骤</el-tag>
    <el-tag v-if="contentBadge" size="small" disable-transitions>→内容</el-tag>
    <el-tag v-if="reviewTag" size="small" type="warning" effect="plain" disable-transitions>待确认</el-tag>
    <span class="tr-spacer" />
    <span v-if="showHoverActions" class="tr-actions" @click.stop>
      <el-button text size="small" :disabled="!canMoveUp" title="上移" @click="emit('move', -1)">↑</el-button>
      <el-button text size="small" :disabled="!canMoveDown" title="下移" @click="emit('move', 1)">↓</el-button>
      <el-button text size="small" type="danger" title="删除" @click="emit('remove')">✕</el-button>
    </span>
  </div>
</template>

<style scoped>
.tr {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 4px 8px;
  cursor: pointer;
  border-bottom: 1px solid var(--el-border-color-lighter, #f0f0f0);
  font-size: 13px;
}
.tr:hover { background: #f5f7fa; }
.tr--selected { background: #ecf5ff; }
.tr-check { flex: none; }
.tr-tag { flex: none; }
.tr-num { color: #409eff; font-weight: 600; font-variant-numeric: tabular-nums; flex: none; }
.tr-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #303133; }
.tr-title--empty { color: #c0c4cc; font-style: italic; }
.tr-spacer { flex: 1; }
.tr-actions { display: none; flex: none; gap: 2px; }
.tr:hover .tr-actions { display: inline-flex; }
.tr--selected .tr-actions { display: inline-flex; }
</style>
