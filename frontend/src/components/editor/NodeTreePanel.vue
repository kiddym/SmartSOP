<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import NodeTreeRow from './NodeTreeRow.vue'
import { useNodeEditorStore } from '@/store/nodeEditor'
import { buildSelection } from '@/utils/batchMark'
import { nextReviewId } from '@/utils/reviewNav'
import { computeReorder, type DropPosition } from '@/utils/nodeTreeDnd'
import type { TreeRow } from '@/utils/nodeTree'

const props = withDefaults(defineProps<{ readonly?: boolean }>(), { readonly: false })

const store = useNodeEditorStore()
const anchor = ref<string | null>(null)
const dragId = ref<string | null>(null)
const dropOnId = ref<string | null>(null)
const dropPos = ref<DropPosition>('before')

const search = computed({ get: () => store.search, set: (v: string) => (store.search = v) })

function onSelect(id: string): void {
  store.select(id)
}
function onChip(id: string, command: string): void {
  if (command === 'l0') void store.setLevel(id, null)
  else if (command === 'l1') void store.setLevel(id, 1)
  else if (command === 'l2') void store.setLevel(id, 2)
  else if (command === 'l3') void store.setLevel(id, 3)
  else if (command === 'step') void store.setKind(id, 'step')
  else if (command === 'node') void store.setKind(id, 'node')
}
function onCheck(id: string, shift: boolean): void {
  const rows = store.rows.map((r) => ({ id: r.node.id, parent_id: r.node.parent_id, kind: r.node.kind }))
  const res = buildSelection({ current: store.selection, anchor: anchor.value, rows, rowId: id, shift })
  store.selection = res.selection
  anchor.value = res.anchor
  for (const wmsg of res.warnings) ElMessage.warning(wmsg)
}
function addNode(): void {
  void store.createNode({ heading_level: null, kind: 'node' })
}
function gotoNextReview(): void {
  const id = nextReviewId(
    store.rows.map((r) => ({ id: r.node.id, mark_status: r.node.mark_status })),
    store.selectedId,
  )
  if (id) store.select(id)
}

// γ 浮动条
const selectedIds = computed(() => [...store.selection])
function clearSel(): void {
  store.selection = new Set()
  anchor.value = null
}
async function barLevel(level: number | null): Promise<void> {
  await store.batchSetLevel(selectedIds.value, level)
  clearSel()
}
async function barStep(): Promise<void> {
  await store.batchSetKind(selectedIds.value, 'step')
  clearSel()
}

// 拖拽
function onDragStart(id: string): void {
  dragId.value = id
}
function onDragOver(id: string, ev: DragEvent): void {
  const el = ev.currentTarget as HTMLElement | null
  if (!el) return
  const rect = el.getBoundingClientRect()
  dropOnId.value = id
  dropPos.value = ev.clientY - rect.top < rect.height / 2 ? 'before' : 'after'
}
function onDrop(id: string): void {
  if (dragId.value && dragId.value !== id) {
    // 仅当 dragover 命中同一行时用算出的 before/after，否则默认 after（含未模拟 dragover 的单测）。
    const pos: DropPosition = dropOnId.value === id ? dropPos.value : 'after'
    const ordered = computeReorder(store.nodes, dragId.value, id, pos)
    void store.reorder(ordered)
  }
  onDragEnd()
}
function onDragEnd(): void {
  dragId.value = null
  dropOnId.value = null
}
function hintFor(row: TreeRow): '' | 'before' | 'after' {
  return dropOnId.value === row.node.id ? dropPos.value : ''
}
</script>

<template>
  <div class="node-tree">
    <div class="np-toolbar">
      <el-input v-model="search" class="np-search" size="small" placeholder="搜索标题…" clearable />
      <el-button v-if="!props.readonly" class="np-add" size="small" @click="addNode">＋ 新增节点</el-button>
      <span class="np-review-count">待确认 {{ store.reviewCount }}</span>
      <el-button
        class="np-review-toggle"
        size="small"
        :type="store.reviewOnly ? 'primary' : 'default'"
        @click="store.reviewOnly = !store.reviewOnly"
      >
        仅看待确认
      </el-button>
      <el-button class="np-review-next" size="small" :disabled="!store.reviewCount" @click="gotoNextReview">下一个</el-button>
    </div>

    <div v-if="!props.readonly && store.selection.size" class="np-bar">
      <span>已选 {{ store.selection.size }}</span>
      <el-button class="np-bar-text" size="small" @click="barLevel(null)">设为正文</el-button>
      <el-button class="np-bar-l1" size="small" @click="barLevel(1)">设为 L1</el-button>
      <el-button class="np-bar-l2" size="small" @click="barLevel(2)">设为 L2</el-button>
      <el-button class="np-bar-l3" size="small" @click="barLevel(3)">设为 L3</el-button>
      <el-button class="np-bar-step" size="small" @click="barStep">设为步骤</el-button>
      <el-button size="small" text @click="clearSel">清空选择</el-button>
    </div>

    <div class="np-rows">
      <NodeTreeRow
        v-for="row in store.rows"
        :key="row.node.id"
        :row="row"
        :readonly="props.readonly"
        :selected="store.selectedId === row.node.id"
        :selected-for-mark="store.selection.has(row.node.id)"
        :drop-hint="hintFor(row)"
        @select="onSelect(row.node.id)"
        @toggle="store.toggleExpand(row.node.id)"
        @check="(shift: boolean) => onCheck(row.node.id, shift)"
        @chip="(c: string) => onChip(row.node.id, c)"
        @remove="store.removeNode(row.node.id)"
        @dragstart="onDragStart(row.node.id)"
        @dragover="(ev: DragEvent) => onDragOver(row.node.id, ev)"
        @drop="onDrop(row.node.id)"
        @dragend="onDragEnd"
      />
      <el-empty v-if="!store.rows.length" description="暂无节点" />
    </div>
  </div>
</template>

<style scoped>
.node-tree { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.np-toolbar { display: flex; align-items: center; gap: 8px; padding: 8px; flex-wrap: wrap; border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5); }
.np-search { width: 180px; }
.np-review-count { font-size: 12px; color: #b88230; }
.np-bar { display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: var(--el-color-primary-light-9, #fbf1ee); flex-wrap: wrap; }
.np-rows { flex: 1; overflow-y: auto; min-height: 0; }
</style>
