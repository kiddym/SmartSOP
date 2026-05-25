<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useDebounceFn, useVirtualList } from '@vueuse/core'
import { ElMessage, ElMessageBox } from 'element-plus'
import TreeRow from './TreeRow.vue'
import EditorLayerMarking from './EditorLayerMarking.vue'
import { useProcedureEditorStore } from '@/store/procedureEditor'
import { getAddButtonState, isTempId } from '@/utils/editor'
import { nextReviewId } from '@/utils/reviewNav'
import type { EditorChapter, EditorStep, FlatRow, NodeKind } from '@/types/node'

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

function addStateFor(row: FlatRow) {
  return store.addButtonStateFor(row.id)
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

// ---- 拖拽 ---- //
const dragId = ref<string | null>(null)
const overId = ref<string | null>(null)
const overHint = ref<'' | 'before' | 'after' | 'inside' | 'invalid'>('')
function resetDrag(): void {
  dragId.value = null
  overId.value = null
  overHint.value = ''
}
function kindOf(id: string): NodeKind {
  const c = store.chapterMap.get(id)
  if (c) return c.content_type === 'content' ? 'content' : 'chapter'
  return 'step'
}
function siblingsOf(parentId: string | null, asChapter: boolean): (EditorChapter | EditorStep)[] {
  const cmp = (a: { sort_order: number; id: string }, b: { sort_order: number; id: string }): number =>
    a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
  return asChapter
    ? [...store.chapters.filter((c) => c.parent_id === parentId)].sort(cmp)
    : [...store.steps.filter((s) => s.chapter_id === parentId)].sort(cmp)
}
// 被拖章节子树的章节嵌套高度（仅计 content_type==='chapter'；content/step 为叶子不计）。
function subtreeChapterHeight(id: string): number {
  const kids = store.chapters.filter((c) => c.parent_id === id && c.content_type === 'chapter')
  return kids.length ? 1 + Math.max(...kids.map((k) => subtreeChapterHeight(k.id))) : 1
}
function validDrop(id: string, target: FlatRow, hint: 'before' | 'after' | 'inside'): boolean {
  if (id === target.id) return false
  const parentId = hint === 'inside' ? target.id : target.parent_id
  const dragged = kindOf(id)
  // 不得拖入自身子树（章节循环）。
  if (store.chapterMap.has(id)) {
    const sub = store.collectSubtree(id)
    if (parentId && sub.has(parentId)) return false
  }
  // 'inside' 仅对 chapter 容器有效。
  if (hint === 'inside' && target.kind !== 'chapter') return false
  // 章节最大嵌套 3 级（§2.4 / CHAPTER_DEPTH_EXCEEDED）：新位层级 + 子树高度 - 1 ≤ 3。
  if (dragged === 'chapter') {
    const parentLevel = parentId ? (store.levelMap.get(parentId) ?? 1) : 0
    if (parentLevel + 1 + subtreeChapterHeight(id) - 1 > 3) return false
  }
  // Q25：目标 parent 现有子类型（排除被拖节点）+ 被拖类型不得混排。
  const kinds: NodeKind[] = []
  for (const c of store.chapters)
    if (c.parent_id === parentId && c.id !== id) kinds.push(c.content_type === 'content' ? 'content' : 'chapter')
  for (const s of store.steps) if (s.chapter_id === parentId && s.id !== id) kinds.push('step')
  const st = getAddButtonState(kinds)
  if (dragged === 'step') return st.canAddStep
  if (dragged === 'content') return st.canAddContent
  return st.canAddChapter
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
  overHint.value = validDrop(dragId.value, row, hint) ? hint : 'invalid'
}
async function onDrop(row: FlatRow): Promise<void> {
  const id = dragId.value
  const hint = overHint.value
  resetDrag()
  if (!id || hint === '' || hint === 'invalid') return
  const asChapter = store.chapterMap.has(id)
  const parentId = hint === 'inside' ? row.id : row.parent_id
  const others = siblingsOf(parentId, asChapter).filter((n) => n.id !== id)
  let index: number
  if (hint === 'inside') index = others.length
  else {
    const ti = others.findIndex((n) => n.id === row.id)
    index = (ti < 0 ? others.length : ti) + (hint === 'after' ? 1 : 0)
  }
  const currentParent = asChapter
    ? store.chapterMap.get(id)!.parent_id
    : store.stepMap.get(id)!.chapter_id
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
  const sel = new Set(markSel.value)
  if (shift && lastChecked.value) {
    const rows = visibleRows.value
    const a = rows.findIndex((r) => r.id === lastChecked.value)
    const b = rows.findIndex((r) => r.id === row.id)
    if (a >= 0 && b >= 0) {
      const [lo, hi] = a < b ? [a, b] : [b, a]
      const anchorParent = rows[a].parent_id
      let crossed = false
      for (let i = lo; i <= hi; i++) {
        const r = rows[i]
        if (r.kind === 'step') continue
        if (r.parent_id !== anchorParent) {
          crossed = true
          continue
        }
        sel.add(r.id)
      }
      if (crossed) ElMessage.warning('范围跨越了不同父节点，跨父部分已忽略')
    }
  } else {
    if (sel.has(row.id)) sel.delete(row.id)
    else sel.add(row.id)
    lastChecked.value = row.id
  }
  if (sel.size > 100) {
    ElMessage.warning('单次最多标记 100 项，请分批操作')
    return
  }
  markSel.value = sel
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
          :can-promote="row.kind !== 'step' && store.canPromoteChapter(row.id)"
          :can-demote="row.kind !== 'step' && store.canDemoteChapter(row.id)"
          :drop-hint="overId === row.id ? overHint : ''"
          @select="onSelect(row)"
          @toggle="store.toggleExpanded(row.id)"
          @add="(kind) => onAdd(row.id, kind)"
          @move="(dir) => store.reorder(row.id, dir)"
          @promote="void store.promoteChapter(row.id)"
          @demote="void store.demoteChapter(row.id)"
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
.tree-scroll {
  flex: 1;
  overflow-y: auto;
}
</style>
