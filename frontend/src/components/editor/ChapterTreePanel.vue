<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useDebounceFn, useVirtualList } from '@vueuse/core'
import { ElMessage, ElMessageBox } from 'element-plus'
import TreeRow from './TreeRow.vue'
import EditorLayerMarking from './EditorLayerMarking.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { isTempId } from '@/utils/editor'
import { nextReviewId, nextRowId } from '@/utils/reviewNav'
import { buildSelection } from '@/utils/batchMark'
import { computeDrop, validDrop, type DndTree } from '@/utils/treeDnd'
import type { EditorChapter, EditorStep, FlatRow } from '@/types/node'

const store = useProcedureEditorStore()

const reviewCount = computed(() => store.chapters.filter((c) => c.mark_status === 'review').length)

// ---- 搜索（debounce 200ms，匹配保留 ancestor，非空时展开全部） ---- //
const search = ref('')
const debounced = ref('')
const setDebounced = useDebounceFn((v: string) => {
  debounced.value = v
  if (v.trim()) store.expandAll()
}, 200)
watch(search, (v) => setDebounced(v))

function rowParent(id: string): string | null {
  const c = store.chapterMap.get(id)
  if (c) return c.parent_id
  return store.stepMap.get(id)?.chapter_id ?? null
}

// ---- review 过滤 + 导航 ---- //
const reviewFilter = ref(false)

// ---- 缺标题过滤 + 导航 ---- //
const missingFilter = ref(false)
function gotoNextMissing(): void {
  const id = nextRowId(store.flatRows, store.selectedId, (r) => r.kind === 'chapter' && !r.title.trim())
  if (id) store.selectNode(id)
}

function keepWithAncestors(rows: FlatRow[], pred: (r: FlatRow) => boolean): FlatRow[] {
  const keep = new Set<string>()
  for (const r of rows) if (pred(r)) keep.add(r.id)
  for (const id of [...keep]) {
    let pid = rowParent(id)
    while (pid) {
      keep.add(pid)
      pid = rowParent(pid)
    }
  }
  return rows.filter((r) => keep.has(r.id))
}

function gotoNextReview(): void {
  const id = nextReviewId(store.flatRows, store.selectedId)
  if (id) store.selectNode(id)
}

function acceptAll(): void {
  if (!reviewCount.value) return
  ElMessageBox.confirm(`将接受 ${reviewCount.value} 个待确认节点，确认其解析结构无误？`, '全部接受', {
    type: 'warning',
  })
    .then(() => store.acceptAllReviews())
    .catch(() => {})
}

const visibleRows = computed<FlatRow[]>(() => {
  let rows = store.flatRows
  if (reviewFilter.value) rows = keepWithAncestors(rows, (r) => r.mark_status === 'review')
  if (missingFilter.value) rows = keepWithAncestors(rows, (r) => r.kind === 'chapter' && !r.title.trim())
  const q = debounced.value.trim().toLowerCase()
  if (q) rows = keepWithAncestors(rows, (r) => `${r.code} ${r.title} ${r.fallback}`.toLowerCase().includes(q))
  return rows
})

const VIRTUAL_THRESHOLD = 50

// ---- 虚拟滚动（节点 > 50 自动；小树直接渲染，避免容器未测高时窗口为空） ---- //
const { list, containerProps, wrapperProps } = useVirtualList(visibleRows, { itemHeight: 30 })
const renderedRows = computed<FlatRow[]>(() => {
  if (visibleRows.value.length <= VIRTUAL_THRESHOLD) return visibleRows.value
  return list.value.map((item) => item.data)
})
const useVirtualRows = computed(() => visibleRows.value.length > VIRTUAL_THRESHOLD)

// 同组首/末判定（上下移按钮 disabled）。
const moveFlags = computed(() => {
  const flags = new Map<string, { up: boolean; down: boolean }>()
  const cmp = (a: { sort_order: number; id: string }, b: { sort_order: number; id: string }): number =>
    a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
  const chByParent = new Map<string | null, EditorChapter[]>()
  for (const c of store.chapters) {
    const g = chByParent.get(c.parent_id) ?? []
    g.push(c)
    chByParent.set(c.parent_id, g)
  }
  const stByChapter = new Map<string | null, EditorStep[]>()
  for (const s of store.steps) {
    const g = stByChapter.get(s.chapter_id) ?? []
    g.push(s)
    stByChapter.set(s.chapter_id, g)
  }
  for (const g of [...chByParent.values(), ...stByChapter.values()]) {
    g.sort(cmp)
    g.forEach((n, i) => flags.set(n.id, { up: i > 0, down: i < g.length - 1 }))
  }
  return flags
})

function addTargetFor(row: FlatRow): { parentId: string | null; afterId: string | null } {
  if (row.kind === 'chapter') return { parentId: row.id, afterId: null }
  return { parentId: row.parent_id, afterId: row.id }
}
function addStateFor(row: FlatRow) {
  return store.addButtonStateFor(addTargetFor(row).parentId)
}
const rootAddState = computed(() => store.addButtonStateFor(null))

// ---- 节点操作 ---- //
function onSelect(row: FlatRow): void {
  if (store.markMode && row.kind !== 'step') void store.cycleMark(row.id)
  else store.selectNode(row.id)
}
function onAdd(parentId: string | null, kind: 'chapter' | 'content' | 'step'): void {
  if (kind === 'step') store.addStepNode(parentId)
  else store.addChapterNode(parentId, kind)
}
function onAddFromRow(row: FlatRow, kind: 'chapter' | 'content' | 'step'): void {
  const { parentId, afterId } = addTargetFor(row)
  if (kind === 'step') store.addStepNode(parentId, afterId)
  else store.addChapterNode(parentId, kind, afterId)
}
async function onRemove(row: FlatRow): Promise<void> {
  if (!isTempId(row.id)) {
    try {
      await ElMessageBox.confirm('删除将软删该节点及其全部子节点，不可撤销。确定删除？', '删除确认', {
        type: 'warning',
      })
    } catch {
      return
    }
  }
  try {
    await store.deleteNode(row.id)
    ElMessage.success('已删除')
  } catch {
    /* 拦截器已提示 */
  }
}

// ---- 拖拽（纯决策见 utils/treeDnd） ---- //
const dndTree = computed<DndTree>(() => ({
  chapters: store.chapters,
  steps: store.steps,
  levelMap: store.levelMap,
}))
const dragId = ref<string | null>(null)
const overId = ref<string | null>(null)
const overHint = ref<'' | 'before' | 'after' | 'inside' | 'invalid'>('')
function resetDrag(): void {
  dragId.value = null
  overId.value = null
  overHint.value = ''
}
function onDragStart(row: FlatRow, ev: DragEvent): void {
  dragId.value = row.id
  ev.dataTransfer?.setData('text/plain', row.id)
  if (ev.dataTransfer) ev.dataTransfer.effectAllowed = 'move'
}
function onDragOver(row: FlatRow, ev: DragEvent): void {
  if (!dragId.value || dragId.value === row.id) {
    overId.value = null
    return
  }
  const rect = (ev.currentTarget as HTMLElement).getBoundingClientRect()
  const ratio = (ev.clientY - rect.top) / rect.height
  const hint: 'before' | 'after' | 'inside' =
    row.kind === 'chapter' && ratio > 0.3 && ratio < 0.7 ? 'inside' : ratio < 0.5 ? 'before' : 'after'
  overId.value = row.id
  overHint.value = validDrop(dndTree.value, dragId.value, row, hint) ? hint : 'invalid'
}
async function onDrop(row: FlatRow): Promise<void> {
  const id = dragId.value
  const hint = overHint.value
  resetDrag()
  if (!id || hint === '' || hint === 'invalid') return
  const { parentId, index, currentParent } = computeDrop(dndTree.value, id, row, hint)
  if (parentId === currentParent) {
    store.reorderWithin(id, index)
    return
  }
  try {
    await ElMessageBox.confirm('跨节点移动会先保存当前改动并提交服务器，不可撤销。是否继续？', '移动确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await store.moveCrossParent(id, parentId, index)
    ElMessage.success('已移动')
  } catch {
    /* 拦截器已提示 */
  }
}

// ---- 标记模式批量选择 ---- //
const markSel = ref<Set<string>>(new Set())
const lastChecked = ref<string | null>(null)
watch(
  () => store.markMode,
  (on) => {
    if (!on) {
      markSel.value = new Set()
      lastChecked.value = null
    }
  },
)
function onCheck(row: FlatRow, shift: boolean): void {
  const res = buildSelection({
    current: markSel.value,
    anchor: lastChecked.value,
    rows: visibleRows.value,
    rowId: row.id,
    shift,
  })
  markSel.value = res.selection
  lastChecked.value = res.anchor
  for (const w of res.warnings) ElMessage.warning(w)
}
async function applyBatch(status: 'step' | 'content'): Promise<void> {
  const ids = [...markSel.value]
  // 先保存待存改动，把临时 id 解析为真实 id，再逐个写后端（避免 404 + 标记静默丢失）。
  const map = await store.ensureSaved()
  for (const id of ids) await store.setMark(map[id] ?? id, status)
  ElMessage.success(`已标记 ${ids.length} 项`)
  markSel.value = new Set()
}
async function clearMarks(): Promise<void> {
  await store.ensureSaved()
  for (const n of store.markedNodes) await store.setMark(n.id, 'unmarked')
  markSel.value = new Set()
}
async function applyMarks(): Promise<void> {
  const marked = store.markedNodes
  if (marked.length === 0) {
    ElMessage.warning('没有需要应用的标记')
    return
  }
  const stepMarks = marked.filter((m) => m.mark_status === 'step')
  const chToStep = stepMarks.filter((m) => m.content_type !== 'content').length
  const ctToSteps = stepMarks.filter((m) => m.content_type === 'content').length
  try {
    await ElMessageBox.confirm(
      `将转换 ${chToStep} 个章节为步骤、拆分 ${ctToSteps} 个内容块为步骤。该操作原子执行且不可撤销，是否继续？`,
      '应用标记',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await store.applyAllMarks()
    ElMessage.success('已应用标记')
  } catch {
    /* 拦截器已提示 */
  }
}

const searchRef = ref<{ focus: () => void } | null>(null)
function focusSearch(): void {
  searchRef.value?.focus()
}
defineExpose({ focusSearch })
</script>

<template>
  <div class="tree-panel">
    <div class="tree-toolbar">
      <el-input
        ref="searchRef"
        v-model="search"
        size="small"
        placeholder="搜索章节 / 步骤（/ 聚焦）"
        clearable
      />
      <div v-if="reviewCount" class="review-bar">
        <span class="review-count" title="解析存疑，待确认">⚠ {{ reviewCount }} 个待确认</span>
        <el-button size="small" @click="gotoNextReview">下一个</el-button>
        <el-button size="small" type="primary" plain @click="acceptAll">全部接受</el-button>
        <el-checkbox v-model="reviewFilter" size="small">只看待确认</el-checkbox>
      </div>
      <div v-if="store.editable && store.missingTitleCount" class="missing-bar">
        <span class="missing-count" title="章节标题为空">⚠ {{ store.missingTitleCount }} 个章节缺标题</span>
        <el-button size="small" @click="gotoNextMissing">下一个</el-button>
        <el-checkbox v-model="missingFilter" size="small">只看缺标题</el-checkbox>
      </div>
      <div v-if="store.editable && !store.markMode" class="root-add">
        <span class="root-add-label">根级：</span>
        <el-button size="small" :disabled="!rootAddState.canAddChapter" @click="onAdd(null, 'chapter')">
          +章节
        </el-button>
        <el-button size="small" :disabled="!rootAddState.canAddContent" @click="onAdd(null, 'content')">
          +内容
        </el-button>
        <el-button size="small" :disabled="!rootAddState.canAddStep" @click="onAdd(null, 'step')">
          +步骤
        </el-button>
      </div>
      <div v-if="store.editable" class="layer-entry">
        <el-button size="small" :type="store.layerMode ? 'primary' : ''" @click="store.toggleLayerMode()">
          {{ store.layerMode ? '退出层级标定' : '层级标定' }}
        </el-button>
      </div>
      <div v-if="store.markMode" class="mark-bar">
        <el-button size="small" type="success" :disabled="markSel.size === 0" @click="applyBatch('step')">
          标记为步骤
        </el-button>
        <el-button size="small" :disabled="markSel.size === 0" @click="applyBatch('content')">
          标记为内容
        </el-button>
        <el-button size="small" @click="clearMarks">清除标记</el-button>
        <el-button size="small" type="primary" @click="applyMarks">应用标记</el-button>
      </div>
    </div>

    <EditorLayerMarking v-if="store.layerMode" />
    <div v-else v-bind="containerProps" class="tree-scroll">
      <div v-bind="useVirtualRows ? wrapperProps : {}">
        <TreeRow
          v-for="row in renderedRows"
          :key="row.id"
          :row="row"
          :selected="store.selectedId === row.id"
          :mark-mode="store.markMode"
          :selected-for-mark="markSel.has(row.id)"
          :add-state="addStateFor(row)"
          :editable="store.editable"
          :can-move-up="moveFlags.get(row.id)?.up ?? false"
          :can-move-down="moveFlags.get(row.id)?.down ?? false"
          :drop-hint="overId === row.id ? overHint : ''"
          @select="onSelect(row)"
          @toggle="store.toggleExpanded(row.id)"
          @add="(kind) => onAddFromRow(row, kind)"
          @move="(dir) => store.reorder(row.id, dir)"
          @remove="onRemove(row)"
          @check="(shift) => onCheck(row, shift)"
          @dragstart="(ev) => onDragStart(row, ev)"
          @dragover="(ev) => onDragOver(row, ev)"
          @drop="onDrop(row)"
          @dragend="resetDrag"
        />
      </div>
      <el-empty v-if="visibleRows.length === 0" description="暂无节点" :image-size="60" />
    </div>
  </div>
</template>

<style scoped>
.tree-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-right: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.tree-toolbar {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5);
}
.layer-entry,
.root-add,
.mark-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.root-add-label {
  font-size: 12px;
  color: #909399;
}
.review-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.review-count {
  font-size: 12px;
  color: #e6a23c;
}
.missing-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.missing-count {
  font-size: 12px;
  color: #b8860b;
}
.tree-scroll {
  flex: 1;
  overflow-y: auto;
}
</style>
