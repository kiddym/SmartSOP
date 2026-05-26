<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useDebounceFn, useVirtualList } from '@vueuse/core'
import { ElMessage, ElMessageBox } from 'element-plus'
import TreeRow from './TreeRow.vue'
import EditorLayerMarking from './EditorLayerMarking.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { isTempId } from '@/utils/editor'
import { nextReviewId, nextRowId } from '@/utils/reviewNav'
import { buildSelection, buildCascadeSelection } from '@/utils/batchMark'
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
  // 用 chapterDocRows（与折叠无关），并展开祖先把目标滚入可见。
  const id = nextRowId(store.chapterDocRows, store.selectedId, (r) => r.kind === 'chapter' && !r.title.trim())
  if (id) {
    store.expandAncestors(id)
    store.selectNode(id)
  }
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
  // step 行和 content 行都在所属 chapter 的同级插入，位置在该行之后
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
  if (kind === 'chapter') store.addChapterNode(parentId)
  else if (kind === 'step') store.addStepNode(parentId, null, 'step')
  else store.addStepNode(parentId, null, 'content')
}
function onAddFromRow(row: FlatRow, kind: 'chapter' | 'content' | 'step'): void {
  const { parentId, afterId } = addTargetFor(row)
  if (kind === 'chapter') store.addChapterNode(parentId, afterId)
  else if (kind === 'step') store.addStepNode(parentId, afterId, 'step')
  else store.addStepNode(parentId, afterId, 'content')
}
function onConvert(row: FlatRow, dir: 'to-step' | 'to-content'): void {
  store.setStepKind(row.id, dir === 'to-step' ? 'step' : 'content')
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

// ---- 标记模式：后代映射（DFS 全子树，忽略折叠/过滤） ---- //
// 每个 chapter id → 其全部后代 id（含 chapter / content / step）。
// rebuild 触发：chapters / steps 任意属性变（结构 + 非结构，Pinia 响应式追踪）。
const descendantsByChapter = computed<Map<string, string[]>>(() => {
  const childChapters = new Map<string | null, string[]>()
  for (const c of store.chapters) {
    const g = childChapters.get(c.parent_id) ?? []
    g.push(c.id)
    childChapters.set(c.parent_id, g)
  }
  const childSteps = new Map<string | null, string[]>()
  for (const s of store.steps) {
    const g = childSteps.get(s.chapter_id) ?? []
    g.push(s.id)
    childSteps.set(s.chapter_id, g)
  }
  const out = new Map<string, string[]>()
  const dfs = (id: string): string[] => {
    const acc: string[] = []
    for (const cid of childChapters.get(id) ?? []) {
      acc.push(cid, ...dfs(cid))
    }
    for (const sid of childSteps.get(id) ?? []) {
      acc.push(sid)
    }
    return acc
  }
  for (const c of store.chapters) out.set(c.id, dfs(c.id))
  return out
})

// 半选集合：descendant 命中数 ∈ (0, total) 的 chapter id。chapter 自身是否在 selection 不影响半选判定。
const indeterminateSet = computed<Set<string>>(() => {
  const out = new Set<string>()
  for (const [chId, desc] of descendantsByChapter.value) {
    if (desc.length === 0) continue
    let hit = 0
    for (const id of desc) if (markSel.value.has(id)) hit++
    if (hit > 0 && hit < desc.length) out.add(chId)
  }
  return out
})

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
  // 章节 + 非 shift：级联。action 由当前状态判定——checked → deselect；其它（unchecked / indeterminate）→ select。
  if (row.kind === 'chapter' && !shift) {
    const desc = descendantsByChapter.value.get(row.id) ?? []
    const isChecked = markSel.value.has(row.id) && !indeterminateSet.value.has(row.id)
    const action: 'select' | 'deselect' = isChecked ? 'deselect' : 'select'
    const res = buildCascadeSelection({
      current: markSel.value,
      anchor: lastChecked.value,
      rootId: row.id,
      descendantIds: desc,
      action,
    })
    markSel.value = res.selection
    lastChecked.value = res.anchor
    for (const w of res.warnings) ElMessage.warning(w)
    return
  }
  // 其它情况（叶子 / shift）：走原 buildSelection
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
  // 先保存待存改动并拿到 temp→real id 映射；再按行 kind 分发。
  const map = await store.ensureSaved()
  let inplace = 0
  for (const id of ids) {
    const real = map[id] ?? id
    const ch = store.chapterMap.get(real)
    if (ch) {
      await store.setMark(real, status)
      continue
    }
    const st = store.stepMap.get(real)
    if (st && st.kind !== status) {
      store.setStepKind(real, status)
      inplace++
    }
    // 已是目标 kind 的 step/content：跳过
  }
  ElMessage.success(`已标记 ${ids.length} 项${inplace ? `（${inplace} 项就地转换）` : ''}`)
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
  const chToStep = marked.filter((m) => m.mark_status === 'step').length
  try {
    await ElMessageBox.confirm(
      `将转换 ${chToStep} 个章节为步骤。该操作原子执行且不可撤销，是否继续？`,
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
      <div v-if="store.editable" class="structure-tools">
        <span class="structure-tools-label">结构工具：</span>
        <el-button
          size="small"
          :type="store.markMode ? 'primary' : 'default'"
          @click="store.toggleMarkMode()"
        >
          {{ store.markMode ? '退出标记模式' : '标记模式' }}
        </el-button>
        <el-button
          size="small"
          :type="store.layerMode ? 'primary' : 'default'"
          @click="store.toggleLayerMode()"
        >
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
          :indeterminate="indeterminateSet.has(row.id)"
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
          @convert="(dir) => onConvert(row, dir)"
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
.structure-tools,
.root-add,
.mark-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.structure-tools-label {
  font-size: 12px;
  color: #909399;
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
