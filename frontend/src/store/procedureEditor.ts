// 编辑器集中状态（§17.2-17.3 / Q153-Q155）。
//
// 变更模型：
//   · 批量/本地/可撤销（经 PUT 保存）：新增、改字段、跳号、同级上下移 → 进脏集 + undo 快照。
//   · 立即后端（确认 + 先存待存改动 + 同步）：删除已存节点、5 种转换、apply-marks、跨 parent 移动。
// 编号 code 用 utils.recomputeCodes 客户端镜像实时预览；保存用 id_map 就地改名，避免整页刷新。

import { defineStore } from 'pinia'
import { fetchProcedureDetail, saveProcedure, applyMarks } from '@/api/procedures'
import {
  convertChapterToStep,
  convertRootToStep,
  convertChapterToContent as convertChapterToContentApi,
  splitChapterTitleContent as splitChapterTitleContentApi,
  setChapterMarkStatus,
} from '@/api/chapters'
import { convertStepToChapter } from '@/api/steps'
import {
  computeFallback,
  formatCode,
  genTempId,
  getAddButtonState,
  isTempId,
  recomputeCodes,
} from '@/utils/editor'
import { computeLayerUpdates, type LayerRole, type LayerRow } from '@/utils/layerMark'
import type {
  AddButtonState,
  ChapterTreeNode,
  EditorChapter,
  EditorStep,
  FlatRow,
  FormType,
  InputSchema,
  MarkStatus,
  NodeKind,
  StepOut,
} from '@/types/node'
import type { ProcedureFieldView, ProcedureMeta, ProcedureSaveIn } from '@/types/procedure'

const MAX_UNDO = 50
const COALESCE_MS = 800
const CONTENT_MAX_BYTES = 5 * 1024 * 1024 // 富文本总量上限（CONTENT_TOO_LARGE，§8.2）

function byteLength(s: string): number {
  return typeof TextEncoder !== 'undefined' ? new TextEncoder().encode(s).length : s.length
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

interface Snapshot {
  chapters: EditorChapter[]
  steps: EditorStep[]
  dirtyChapters: string[]
  dirtySteps: string[]
  deletedChapterIds: string[]
  deletedStepIds: string[]
  metaDirty: boolean
}

// sessionStorage 草稿的完整可恢复状态（§7）。
export interface EditorDraftState {
  procedure: ProcedureMeta | null
  chapters: EditorChapter[]
  steps: EditorStep[]
  selectedId: string | null
  expanded: Record<string, boolean>
  dirtyChapters: string[]
  dirtySteps: string[]
  deletedChapterIds: string[]
  deletedStepIds: string[]
  metaDirty: boolean
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function emptyStep(
  chapterId: string | null,
  sortOrder: number,
  kind: 'step' | 'content' = 'step',
): EditorStep {
  return {
    id: genTempId(),
    chapter_id: chapterId,
    kind,
    title: '',
    content: '',
    input_schema: kind === 'content' ? ({} as InputSchema) : { type: 'COMMON' },
    attachment_marks: [],
    skip_numbering: false,
    sort_order: sortOrder,
  }
}

function ingestChapters(tree: ChapterTreeNode[]): EditorChapter[] {
  const out: EditorChapter[] = []
  const walk = (nodes: ChapterTreeNode[], parentId: string | null): void => {
    for (const n of nodes) {
      out.push({
        id: n.id,
        parent_id: parentId,
        title: n.title,
        skip_numbering: n.skip_numbering,
        mark_status: n.mark_status,
        sort_order: n.sort_order,
      })
      walk(n.children, n.id)
    }
  }
  walk(tree, null)
  return out
}

function ingestStep(s: StepOut): EditorStep {
  return {
    id: s.id,
    chapter_id: s.chapter_id,
    kind: s.kind,
    title: s.title,
    content: s.content,
    input_schema: s.input_schema,
    attachment_marks: s.attachment_marks,
    skip_numbering: s.skip_numbering,
    sort_order: s.sort_order,
  }
}

// patch 是否真的改动了目标的任一字段（含数组/对象，按值比较），用于跳过空操作。
function patchChangesAnything(target: Record<string, unknown>, patch: Record<string, unknown>): boolean {
  return Object.keys(patch).some((k) => JSON.stringify(target[k]) !== JSON.stringify(patch[k]))
}

interface State {
  procedure: ProcedureMeta | null
  hasSourceDocx: boolean
  fields: ProcedureFieldView[]
  chapters: EditorChapter[]
  steps: EditorStep[]
  selectedId: string | null
  expanded: Record<string, boolean>
  dirtyChapters: Set<string>
  dirtySteps: Set<string>
  deletedChapterIds: Set<string>
  deletedStepIds: Set<string>
  metaDirty: boolean
  markMode: boolean
  layerMode: boolean
  loading: boolean
  saving: boolean
  loadError: boolean
  undoStack: Snapshot[]
  redoStack: Snapshot[]
  lastUndoTag: string | null
  lastUndoAt: number
  inflightSplit: Set<string>
}

export const useProcedureEditorStore = defineStore('procedureEditor', {
  state: (): State => ({
    procedure: null,
    hasSourceDocx: false,
    fields: [],
    chapters: [],
    steps: [],
    selectedId: null,
    expanded: {},
    dirtyChapters: new Set<string>(),
    dirtySteps: new Set<string>(),
    deletedChapterIds: new Set<string>(),
    deletedStepIds: new Set<string>(),
    metaDirty: false,
    markMode: false,
    layerMode: false,
    loading: false,
    saving: false,
    loadError: false,
    undoStack: [],
    redoStack: [],
    lastUndoTag: null,
    lastUndoAt: 0,
    inflightSplit: new Set<string>(),
  }),

  getters: {
    editable(state): boolean {
      return !!state.procedure && state.procedure.is_current && state.procedure.status === 'DRAFT'
    },
    isDirty(state): boolean {
      return (
        state.dirtyChapters.size > 0
        || state.dirtySteps.size > 0
        || state.deletedChapterIds.size > 0
        || state.deletedStepIds.size > 0
        || state.metaDirty
      )
    },
    revision(state): number {
      return state.procedure?.revision ?? 0
    },
    chapterMap(state): Map<string, EditorChapter> {
      return new Map(state.chapters.map((c) => [c.id, c]))
    },
    stepMap(state): Map<string, EditorStep> {
      return new Map(state.steps.map((s) => [s.id, s]))
    },
    codeMaps(state) {
      return recomputeCodes(state.chapters, state.steps)
    },
    // 章节编号层级（1-based，仅 chapter/content；step 不参与）。
    levelMap(state): Map<string, number> {
      const byParent = new Map<string | null, EditorChapter[]>()
      for (const c of state.chapters) {
        const list = byParent.get(c.parent_id) ?? []
        list.push(c)
        byParent.set(c.parent_id, list)
      }
      const levels = new Map<string, number>()
      const walk = (parentId: string | null, level: number): void => {
        for (const c of byParent.get(parentId) ?? []) {
          levels.set(c.id, level)
          walk(c.id, level + 1)
        }
      }
      walk(null, 1)
      return levels
    },
    // 文档序章节/正文行（层级标定面板数据源）。
    layerRows(): LayerRow[] {
      const levels = this.levelMap
      const hasStep = new Set(this.steps.map((s) => s.chapter_id))
      const byParent = new Map<string | null, EditorChapter[]>()
      for (const c of this.chapters) {
        const g = byParent.get(c.parent_id) ?? []
        g.push(c)
        byParent.set(c.parent_id, g)
      }
      const cmp = (a: EditorChapter, b: EditorChapter): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      const rows: LayerRow[] = []
      const walk = (parent: string | null): void => {
        for (const c of [...(byParent.get(parent) ?? [])].sort(cmp)) {
          rows.push({
            id: c.id,
            level: levels.get(c.id) ?? 1,
            hasLeafChildren: hasStep.has(c.id),
          })
          walk(c.id)
        }
      }
      walk(null)
      return rows
    },
    // 某 parent 直接子节点的类型集合（Q25）；parentId=null 表示根级。
    childKindsOf(): (parentId: string | null) => NodeKind[] {
      return (parentId: string | null): NodeKind[] => {
        const kinds: NodeKind[] = []
        for (const c of this.chapters) {
          if (c.parent_id === parentId) kinds.push('chapter')
        }
        for (const s of this.steps) {
          if (s.chapter_id === parentId) kinds.push(s.kind === 'content' ? 'content' : 'step')
        }
        return kinds
      }
    },
    addButtonStateFor(): (parentId: string | null) => AddButtonState {
      return (parentId: string | null): AddButtonState => getAddButtonState(this.childKindsOf(parentId))
    },
    missingTitleCount(state): number {
      return state.chapters.filter((c) => !c.title.trim()).length
    },
    // 全部「章节/内容」按文档序（与折叠无关，含 title），供缺标题定位/导航——
    // 不能用 flatRows，它会剔除折叠分支里的节点（漏掉藏在折叠章节里的缺标题章节）。
    chapterDocRows(): { id: string; kind: 'chapter' | 'content'; title: string }[] {
      return this.layerRows.map((r) => ({
        id: r.id,
        kind: 'chapter' as const,
        title: this.chapterMap.get(r.id)?.title ?? '',
      }))
    },
    selectedChapter(state): EditorChapter | null {
      return state.selectedId ? (this.chapterMap.get(state.selectedId) ?? null) : null
    },
    selectedStep(state): EditorStep | null {
      return state.selectedId ? (this.stepMap.get(state.selectedId) ?? null) : null
    },
    markedNodes(state): EditorChapter[] {
      return state.chapters.filter((c) => c.mark_status === 'step' || c.mark_status === 'content')
    },
    // 扁平 DFS 行（尊重 expanded）；树渲染 / 虚拟滚动 / 搜索过滤的统一单元。
    flatRows(state): FlatRow[] {
      const chByParent = new Map<string | null, EditorChapter[]>()
      for (const c of state.chapters) {
        const list = chByParent.get(c.parent_id) ?? []
        list.push(c)
        chByParent.set(c.parent_id, list)
      }
      const stByChapter = new Map<string | null, EditorStep[]>()
      for (const s of state.steps) {
        const list = stByChapter.get(s.chapter_id) ?? []
        list.push(s)
        stByChapter.set(s.chapter_id, list)
      }
      const cmp = (a: { sort_order: number; id: string }, b: { sort_order: number; id: string }): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      for (const g of chByParent.values()) g.sort(cmp)
      for (const g of stByChapter.values()) g.sort(cmp)

      const { chapterCodes, stepCodes } = this.codeMaps
      const levels = this.levelMap
      const rows: FlatRow[] = []

      const walk = (parentId: string | null, depth: number): void => {
        for (const ch of chByParent.get(parentId) ?? []) {
          const kind: NodeKind = 'chapter'
          const level = levels.get(ch.id) ?? 1
          const hasChildChapters = (chByParent.get(ch.id)?.length ?? 0) > 0
          const hasChildSteps = (stByChapter.get(ch.id)?.length ?? 0) > 0
          const hasChildren = hasChildChapters || hasChildSteps
          rows.push({
            id: ch.id,
            kind,
            depth,
            parent_id: ch.parent_id,
            title: ch.title,
            code: formatCode({ kind, level, code: chapterCodes.get(ch.id) ?? '', skipNumbering: ch.skip_numbering }),
            skip_numbering: ch.skip_numbering,
            mark_status: ch.mark_status,
            form_type: null,
            has_children: hasChildren,
            expanded: state.expanded[ch.id] ?? false,
            fallback: computeFallback('chapter', ''),
          })
          if (hasChildren && (state.expanded[ch.id] ?? false)) walk(ch.id, depth + 1)
        }
        for (const st of stByChapter.get(parentId) ?? []) {
          const stKind: NodeKind = st.kind === 'content' ? 'content' : 'step'
          rows.push({
            id: st.id,
            kind: stKind,
            depth,
            parent_id: st.chapter_id,
            title: st.title,
            code: formatCode({ kind: stKind, level: 0, code: stepCodes.get(st.id) ?? '', skipNumbering: st.skip_numbering }),
            skip_numbering: st.skip_numbering,
            mark_status: 'unmarked',
            form_type: st.kind === 'content' ? null : ((st.input_schema?.type ?? 'COMMON') as FormType),
            has_children: false,
            expanded: false,
            fallback: computeFallback(stKind, st.content),
          })
        }
      }
      walk(null, 0)
      return rows
    },
  },

  actions: {
    // ---- 加载 ---- //
    async load(id: string): Promise<void> {
      this.loading = true
      this.loadError = false
      try {
        const detail = await fetchProcedureDetail(id)
        this.procedure = detail.procedure
        this.hasSourceDocx = detail.has_source_docx
        this.fields = detail.fields
        this.chapters = ingestChapters(detail.chapters)
        this.steps = detail.steps.map(ingestStep)
        this.resetEditState()
        this.expandAll()
        this.selectedId = this.firstNodeId()
      } catch {
        this.loadError = true
      } finally {
        this.loading = false
      }
    },

    resetEditState(): void {
      this.dirtyChapters = new Set()
      this.dirtySteps = new Set()
      this.deletedChapterIds = new Set()
      this.deletedStepIds = new Set()
      this.metaDirty = false
      this.undoStack = []
      this.redoStack = []
      this.lastUndoTag = null
    },

    firstNodeId(): string | null {
      return this.flatRows[0]?.id ?? null
    },

    expandAll(): void {
      const next: Record<string, boolean> = {}
      for (const c of this.chapters) next[c.id] = true
      this.expanded = next
    },

    selectNode(id: string | null): void {
      this.selectedId = id
    },

    setExpanded(id: string, value: boolean): void {
      this.expanded = { ...this.expanded, [id]: value }
    },

    toggleExpanded(id: string): void {
      this.setExpanded(id, !(this.expanded[id] ?? false))
    },

    // 展开 id 的全部祖先（不含自身），用于把目标滚入可见。
    expandAncestors(id: string): void {
      let pid = this.chapterMap.get(id)?.parent_id ?? this.stepMap.get(id)?.chapter_id ?? null
      while (pid) {
        this.setExpanded(pid, true)
        pid = this.chapterMap.get(pid)?.parent_id ?? null
      }
    },

    // ---- undo 快照 ---- //
    pushUndo(tag?: string): void {
      const now = Date.now()
      if (tag && tag === this.lastUndoTag && now - this.lastUndoAt < COALESCE_MS) {
        this.lastUndoAt = now
        return
      }
      this.undoStack.push(this.snapshot())
      if (this.undoStack.length > MAX_UNDO) this.undoStack.shift()
      this.redoStack = []
      this.lastUndoTag = tag ?? null
      this.lastUndoAt = now
    },

    snapshot(): Snapshot {
      return {
        chapters: clone(this.chapters),
        steps: clone(this.steps),
        dirtyChapters: [...this.dirtyChapters],
        dirtySteps: [...this.dirtySteps],
        deletedChapterIds: [...this.deletedChapterIds],
        deletedStepIds: [...this.deletedStepIds],
        metaDirty: this.metaDirty,
      }
    },

    restore(snap: Snapshot): void {
      this.chapters = clone(snap.chapters)
      this.steps = clone(snap.steps)
      this.dirtyChapters = new Set(snap.dirtyChapters)
      this.dirtySteps = new Set(snap.dirtySteps)
      this.deletedChapterIds = new Set(snap.deletedChapterIds)
      this.deletedStepIds = new Set(snap.deletedStepIds)
      this.metaDirty = snap.metaDirty
      if (this.selectedId && !this.chapterMap.has(this.selectedId) && !this.stepMap.has(this.selectedId)) {
        this.selectedId = this.firstNodeId()
      }
    },

    undo(): void {
      const snap = this.undoStack.pop()
      if (!snap) return
      this.redoStack.push(this.snapshot())
      this.restore(snap)
      this.lastUndoTag = null
    },

    redo(): void {
      const snap = this.redoStack.pop()
      if (!snap) return
      this.undoStack.push(this.snapshot())
      this.restore(snap)
      this.lastUndoTag = null
    },

    // ---- 本地编辑（脏 + 可撤销） ---- //
    updateChapterFields(id: string, patch: Partial<EditorChapter>, undoTag?: string): void {
      const ch = this.chapterMap.get(id)
      if (!ch) return
      if (!patchChangesAnything(ch as unknown as Record<string, unknown>, patch)) return // 空操作不置脏、不入撤销栈
      this.pushUndo(undoTag)
      Object.assign(ch, patch)
      this.dirtyChapters.add(id)
    },

    updateStepFields(id: string, patch: Partial<EditorStep>, undoTag?: string): void {
      const st = this.stepMap.get(id)
      if (!st) return
      if (!patchChangesAnything(st as unknown as Record<string, unknown>, patch)) return // 空操作（如编辑器回发等值内容）不置脏、不入撤销栈
      this.pushUndo(undoTag)
      Object.assign(st, patch)
      this.dirtySteps.add(id)
    },

    setStepFormType(id: string, type: FormType): void {
      const st = this.stepMap.get(id)
      if (!st) return
      this.pushUndo()
      st.input_schema = { type } as InputSchema
      this.dirtySteps.add(id)
    },

    toggleSkipNumbering(id: string): void {
      const ch = this.chapterMap.get(id)
      if (ch) {
        this.updateChapterFields(id, { skip_numbering: !ch.skip_numbering })
        return
      }
      const st = this.stepMap.get(id)
      if (st) this.updateStepFields(id, { skip_numbering: !st.skip_numbering })
    },

    nextSortOrder(siblings: { sort_order: number }[]): number {
      return siblings.reduce((m, s) => Math.max(m, s.sort_order), -1) + 1
    },

    addChapterNode(parentId: string | null, afterId: string | null = null): string {
      this.pushUndo()
      const siblings = this.chapters.filter((c) => c.parent_id === parentId)
      const node: EditorChapter = {
        id: genTempId(),
        parent_id: parentId,
        title: '',
        skip_numbering: false,
        mark_status: 'unmarked',
        sort_order: this.nextSortOrder(siblings),
      }
      this.chapters.push(node)
      this.dirtyChapters.add(node.id)
      if (afterId) {
        const after = this.chapterMap.get(afterId)
        if (after && after.parent_id === parentId) {
          for (const c of this.chapters) {
            if (c.parent_id === parentId && c.id !== node.id && c.sort_order > after.sort_order) {
              c.sort_order += 1
              this.dirtyChapters.add(c.id)
            }
          }
          node.sort_order = after.sort_order + 1
        }
      }
      if (parentId) this.setExpanded(parentId, true)
      this.selectedId = node.id
      return node.id
    },

    addStepNode(
      chapterId: string | null,
      afterId: string | null = null,
      kind: 'step' | 'content' = 'step',
    ): string {
      this.pushUndo()
      const siblings = this.steps.filter((s) => s.chapter_id === chapterId)
      const node = emptyStep(chapterId, this.nextSortOrder(siblings), kind)
      this.steps.push(node)
      this.dirtySteps.add(node.id)
      if (afterId) {
        const after = this.stepMap.get(afterId)
        if (after && after.chapter_id === chapterId) {
          for (const st of this.steps) {
            if (st.chapter_id === chapterId && st.id !== node.id && st.sort_order > after.sort_order) {
              st.sort_order += 1
              this.dirtySteps.add(st.id)
            }
          }
          node.sort_order = after.sort_order + 1
        }
      }
      if (chapterId) this.setExpanded(chapterId, true)
      this.selectedId = node.id
      return node.id
    },

    // 步骤行类型翻转（'step' ↔ 'content'）；content 行不承载执行表单，清空 input_schema/标题/附件标记。
    setStepKind(id: string, kind: 'step' | 'content'): void {
      const st = this.stepMap.get(id)
      if (!st || st.kind === kind) return
      this.pushUndo()
      st.kind = kind
      if (kind === 'content') {
        st.input_schema = {} as InputSchema // content 不用执行表单，与后端一致置空对象
        st.attachment_marks = []
        st.title = ''
      } else {
        st.input_schema = { type: 'COMMON' } as InputSchema
      }
      this.dirtySteps.add(id)
    },

    // 同级上下移（reorder）：在节点所属分组内交换 sort_order。
    reorder(id: string, dir: 'up' | 'down'): void {
      const ch = this.chapterMap.get(id)
      if (ch) {
        const group = this.chapters
          .filter((c) => c.parent_id === ch.parent_id)
          .sort((a, b) => a.sort_order - b.sort_order)
        this.swapInGroup(group, id, dir)
        return
      }
      const st = this.stepMap.get(id)
      if (st) {
        const group = this.steps
          .filter((s) => s.chapter_id === st.chapter_id)
          .sort((a, b) => a.sort_order - b.sort_order)
        this.swapInGroup(group, id, dir)
      }
    },

    swapInGroup(group: { id: string; sort_order: number }[], id: string, dir: 'up' | 'down'): void {
      const idx = group.findIndex((n) => n.id === id)
      const target = dir === 'up' ? idx - 1 : idx + 1
      if (idx < 0 || target < 0 || target >= group.length) return
      this.pushUndo()
      const a = group[idx]
      const b = group[target]
      const tmp = a.sort_order
      a.sort_order = b.sort_order
      b.sort_order = tmp
      const dirtyA = this.chapterMap.has(a.id) ? this.dirtyChapters : this.dirtySteps
      const dirtyB = this.chapterMap.has(b.id) ? this.dirtyChapters : this.dirtySteps
      dirtyA.add(a.id)
      dirtyB.add(b.id)
    },

    // 同 parent 重排到任意 targetIndex（拖拽 reorder，本地可撤销）；重写整组 sort_order = 0..n。
    reorderWithin(id: string, targetIndex: number): void {
      const ch = this.chapterMap.get(id)
      const isChapter = !!ch
      const parentKey = isChapter ? ch!.parent_id : this.stepMap.get(id)?.chapter_id ?? null
      const cmp = (a: EditorChapter | EditorStep, b: EditorChapter | EditorStep): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      const group: (EditorChapter | EditorStep)[] = isChapter
        ? [...this.chapters.filter((c) => c.parent_id === parentKey)].sort(cmp)
        : [...this.steps.filter((s) => s.chapter_id === parentKey)].sort(cmp)
      const from = group.findIndex((n) => n.id === id)
      if (from < 0) return
      this.pushUndo()
      const [moved] = group.splice(from, 1)
      const clamped = Math.max(0, Math.min(targetIndex, group.length))
      group.splice(clamped, 0, moved)
      const dirty = isChapter ? this.dirtyChapters : this.dirtySteps
      group.forEach((n, i) => {
        n.sort_order = i
        dirty.add(n.id)
      })
    },

    // 删除已存节点的纯本地副作用（在后端 DELETE 成功后调用，或对临时节点直接调用）。
    removeNodeLocal(id: string): void {
      const ch = this.chapterMap.get(id)
      if (ch) {
        const ids = this.collectSubtree(id)
        this.chapters = this.chapters.filter((c) => !ids.has(c.id))
        this.steps = this.steps.filter((s) => !(s.chapter_id && ids.has(s.chapter_id)))
        for (const x of ids) {
          this.dirtyChapters.delete(x)
          delete this.expanded[x]
        }
      } else {
        this.steps = this.steps.filter((s) => s.id !== id)
        this.dirtySteps.delete(id)
      }
      if (this.selectedId && !this.chapterMap.has(this.selectedId) && !this.stepMap.has(this.selectedId)) {
        this.selectedId = this.firstNodeId()
      }
    },

    collectSubtree(rootId: string): Set<string> {
      const ids = new Set<string>([rootId])
      let changed = true
      while (changed) {
        changed = false
        for (const c of this.chapters) {
          if (c.parent_id && ids.has(c.parent_id) && !ids.has(c.id)) {
            ids.add(c.id)
            changed = true
          }
        }
      }
      return ids
    },

    // 删除节点：纯本地，已存节点的真实 id（含子树中的已存后代 / 已存步骤）记入待删除集合，
    // 由下次 save 经 buildPayload 一并提交。可撤销。
    deleteNode(id: string): void {
      this.pushUndo()
      const ch = this.chapterMap.get(id)
      if (ch) {
        const subtreeChapterIds = this.collectSubtree(id)
        for (const cid of subtreeChapterIds) {
          if (!isTempId(cid)) this.deletedChapterIds.add(cid)
        }
        for (const st of this.steps) {
          if (st.chapter_id && subtreeChapterIds.has(st.chapter_id) && !isTempId(st.id)) {
            this.deletedStepIds.add(st.id)
          }
        }
      } else if (this.stepMap.has(id)) {
        if (!isTempId(id)) this.deletedStepIds.add(id)
      }
      this.removeNodeLocal(id)
    },

    // ---- 立即后端转换 / 移动 / 标记（不可撤销，先存待存改动） ---- //
    // 返回 id_map：调用方据此把可能仍是临时的 id 解析为真实 id。
    async ensureSaved(): Promise<Record<string, string>> {
      return this.isDirty ? await this.save() : {}
    },

    async reload(): Promise<void> {
      if (!this.procedure) return
      const keep = this.selectedId
      const keepExpanded = { ...this.expanded }
      await this.load(this.procedure.id)
      // 保留用户的展开/折叠意图（仅对仍存在的章节），不被 load() 的 expandAll 覆盖。
      this.expanded = Object.fromEntries(
        Object.entries(keepExpanded).filter(([k]) => this.chapterMap.has(k)),
      )
      if (keep && (this.chapterMap.has(keep) || this.stepMap.has(keep))) this.selectedId = keep
    },

    async convertToStep(id: string): Promise<void> {
      const map = await this.ensureSaved()
      await convertChapterToStep(map[id] ?? id)
      await this.reload()
    },
    async convertRootToStep(id: string): Promise<void> {
      const map = await this.ensureSaved()
      await convertRootToStep(map[id] ?? id)
      await this.reload()
    },
    async convertToChapter(id: string): Promise<void> {
      const map = await this.ensureSaved()
      await convertStepToChapter(map[id] ?? id)
      await this.reload()
    },

    async refreshAfterConversion(): Promise<void> {
      await this.reload()
    },

    async convertChapterToContent(id: string): Promise<void> {
      const map = await this.ensureSaved()
      const realId = map[id] ?? id
      const result = await convertChapterToContentApi(realId)
      await this.refreshAfterConversion()
      this.pushUndo(`chapter-to-content:${realId}`)
      if (result.created.length > 0) this.selectNode(result.created[0])
    },

    async splitChapterTitleContent(id: string, cursorOffset: number): Promise<void> {
      if (this.inflightSplit.has(id)) return
      this.inflightSplit.add(id)
      try {
        const map = await this.ensureSaved()
        const realId = map[id] ?? id
        const result = await splitChapterTitleContentApi(realId, { cursor_offset: cursorOffset })
        await this.refreshAfterConversion()
        this.pushUndo(`split-title-content:${realId}`)
        if (result.created.length > 0) this.selectNode(result.created[0])
      } finally {
        this.inflightSplit.delete(id)
      }
    },

    // 跨父移动：本地写 parent_id (或 chapter_id) + 两侧组重排 sort_order，置脏，可撤销。
    // 客户端 DnD 层（utils/treeDnd.ts）已挡住环 / 三级深度 / Q25 同父类型互斥，store 不再二次校验。
    moveCrossParent(id: string, targetParentId: string | null, targetIndex: number): void {
      const ch = this.chapterMap.get(id)
      const st = ch ? null : this.stepMap.get(id)
      if (!ch && !st) return
      this.pushUndo()
      if (ch) {
        const oldParent = ch.parent_id
        ch.parent_id = targetParentId
        this.resequenceChapterGroup(oldParent)
        this.resequenceChapterGroupWithInsert(targetParentId, id, targetIndex)
      } else {
        const oldChapter = st!.chapter_id
        st!.chapter_id = targetParentId
        this.resequenceStepGroup(oldChapter)
        this.resequenceStepGroupWithInsert(targetParentId, id, targetIndex)
      }
    },

    // 把指定 parent_id 下的章节按当前顺序重写 sort_order = 0..n，全部置脏。
    resequenceChapterGroup(parentId: string | null): void {
      const group = this.chapters
        .filter((c) => c.parent_id === parentId)
        .sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1))
      group.forEach((c, i) => {
        c.sort_order = i
        this.dirtyChapters.add(c.id)
      })
    },

    // 把指定 parent_id 下的章节排序后，将 movedId 插入到 targetIndex，重写 sort_order = 0..n，全部置脏。
    resequenceChapterGroupWithInsert(parentId: string | null, movedId: string, targetIndex: number): void {
      const cmp = (a: EditorChapter, b: EditorChapter): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      const others = this.chapters.filter((c) => c.parent_id === parentId && c.id !== movedId).sort(cmp)
      const moved = this.chapterMap.get(movedId)
      if (!moved) return
      const clamped = Math.max(0, Math.min(targetIndex, others.length))
      others.splice(clamped, 0, moved)
      others.forEach((c, i) => {
        c.sort_order = i
        this.dirtyChapters.add(c.id)
      })
    },

    resequenceStepGroup(chapterId: string | null): void {
      const group = this.steps
        .filter((s) => s.chapter_id === chapterId)
        .sort((a, b) => (a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1))
      group.forEach((st, i) => {
        st.sort_order = i
        this.dirtySteps.add(st.id)
      })
    },

    resequenceStepGroupWithInsert(chapterId: string | null, movedId: string, targetIndex: number): void {
      const cmp = (a: EditorStep, b: EditorStep): number =>
        a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.id < b.id ? -1 : 1
      const others = this.steps.filter((s) => s.chapter_id === chapterId && s.id !== movedId).sort(cmp)
      const moved = this.stepMap.get(movedId)
      if (!moved) return
      const clamped = Math.max(0, Math.min(targetIndex, others.length))
      others.splice(clamped, 0, moved)
      others.forEach((st, i) => {
        st.sort_order = i
        this.dirtySteps.add(st.id)
      })
    },

    // ---- 标记模式 / 层级标定模式（互斥） ---- //
    toggleMarkMode(): void {
      this.markMode = !this.markMode
      if (this.markMode) this.layerMode = false
    },
    toggleLayerMode(): void {
      this.layerMode = !this.layerMode
      if (this.layerMode) this.markMode = false
    },
    applyLayerRoles(roleMap: Map<string, LayerRole>): void {
      const updates = computeLayerUpdates(this.layerRows, roleMap)
      this.pushUndo('layer')
      const clearReview: string[] = []
      const toContent: { id: string; parent_id: string | null; sort_order: number; title: string }[] = []
      // 第一遍：先把所有「仍是章节」的行重排（parent_id/sort_order），并收集要转 content 的行。
      for (const [id, u] of updates) {
        const ch = this.chapterMap.get(id)
        if (!ch) continue
        // 应用层级=对结构的刻意确认，连带清待确认（与 toggleContentType 一致）。
        if (ch.mark_status === 'review') clearReview.push(id)
        if (u.toContentStep) {
          toContent.push({ id, parent_id: u.parent_id, sort_order: u.sort_order, title: ch.title })
          continue
        }
        ch.parent_id = u.parent_id
        ch.sort_order = u.sort_order
        this.dirtyChapters.add(id)
      }
      // 第二遍：把 content 角色的章节转成内容块步骤。此时其原子节点已在第一遍被重排到各自新父级
      // （content 行不更新 l1/l2/l3，故其后代会挂到上一个标题上下文），该章节已无子节点，可安全删除。
      for (const t of toContent) {
        this.removeNodeLocal(t.id)
        const sid = genTempId()
        this.steps.push({
          id: sid,
          chapter_id: t.parent_id,
          kind: 'content',
          title: '',
          content: t.title.trim() ? `<p>${escapeHtml(t.title)}</p>` : '',
          input_schema: {} as InputSchema,
          attachment_marks: [],
          skip_numbering: false,
          sort_order: t.sort_order,
        })
        this.dirtySteps.add(sid)
      }
      this.layerMode = false
      for (const id of clearReview) void this.setMark(id, 'unmarked')
    },

    // 设置单节点 mark_status。调用方须保证 id 为真实 id（临时节点先 ensureSaved 解析）；
    // isTempId 为后端 404 兜底：临时节点只改本地、不发请求（apply-marks 读 DB，故必须先持久化）。
    async setMark(id: string, status: MarkStatus): Promise<void> {
      const ch = this.chapterMap.get(id)
      if (!ch) return
      const prev = ch.mark_status
      ch.mark_status = status
      if (isTempId(id)) return
      try {
        await setChapterMarkStatus(id, status)
      } catch {
        ch.mark_status = prev
      }
    },

    // 接受单个待确认：清 review（保留解析判定的类型/结构）。
    async acceptReview(id: string): Promise<void> {
      await this.setMark(id, 'unmarked')
    },

    // 接受全部待确认。
    async acceptAllReviews(): Promise<void> {
      await this.ensureSaved()
      const ids = this.chapters.filter((c) => c.mark_status === 'review').map((c) => c.id)
      for (const id of ids) await this.setMark(id, 'unmarked')
    },

    async cycleMark(id: string): Promise<void> {
      // 先保存待存改动，把可能的临时 id 解析为真实 id，再写后端（避免 404 + 标记静默丢失）。
      const map = await this.ensureSaved()
      const real = map[id] ?? id
      const ch = this.chapterMap.get(real)
      if (!ch) return
      const order: MarkStatus[] = ['unmarked', 'step', 'content']
      const idx = order.indexOf(ch.mark_status === 'review' ? 'unmarked' : ch.mark_status)
      await this.setMark(real, order[(idx + 1) % order.length])
    },

    async applyAllMarks(): Promise<void> {
      await this.ensureSaved()
      await applyMarks(this.procedure!.id)
      this.markMode = false
      await this.reload()
    },

    // 程序级元字段编辑（详情折叠面板）。不进 undo 栈（undo 聚焦树结构）。
    setMetaField<K extends keyof ProcedureMeta>(key: K, value: ProcedureMeta[K]): void {
      if (!this.procedure) return
      this.procedure[key] = value
      this.metaDirty = true
    },

    // ---- sessionStorage 草稿（§7：导出 / 导入完整可恢复状态） ---- //
    exportDraft(): EditorDraftState {
      return {
        procedure: clone(this.procedure),
        chapters: clone(this.chapters),
        steps: clone(this.steps),
        selectedId: this.selectedId,
        expanded: { ...this.expanded },
        dirtyChapters: [...this.dirtyChapters],
        dirtySteps: [...this.dirtySteps],
        deletedChapterIds: [...this.deletedChapterIds],
        deletedStepIds: [...this.deletedStepIds],
        metaDirty: this.metaDirty,
      }
    },

    importDraft(d: EditorDraftState): void {
      if (d.procedure) this.procedure = clone(d.procedure)
      this.chapters = clone(d.chapters)
      this.steps = clone(d.steps)
      this.selectedId = d.selectedId
      this.expanded = { ...d.expanded }
      this.dirtyChapters = new Set(d.dirtyChapters)
      this.dirtySteps = new Set(d.dirtySteps)
      this.deletedChapterIds = new Set(d.deletedChapterIds)
      this.deletedStepIds = new Set(d.deletedStepIds)
      this.metaDirty = d.metaDirty
      this.undoStack = []
      this.redoStack = []
      this.lastUndoTag = null
    },

    // ---- 客户端保存预校验（§8.2） ---- //
    validateForSave(): string[] {
      const errors: string[] = []
      const emptyChapters = this.chapters.filter((c) => !c.title.trim()).length
      if (emptyChapters > 0) errors.push(`有 ${emptyChapters} 个章节标题为空`)
      const oversized = this.steps.filter((s) => byteLength(s.content) > CONTENT_MAX_BYTES).length
      if (oversized > 0) errors.push(`有 ${oversized} 个节点正文超过 5MB`)
      return errors
    },

    // ---- 保存（PUT 整批；id_map 就地改名） ---- //
    buildPayload(): ProcedureSaveIn {
      const p = this.procedure!
      const chapters = [...this.dirtyChapters]
        .map((id) => this.chapterMap.get(id))
        .filter((c): c is EditorChapter => !!c)
        .map((c) => ({
          id: c.id,
          parent_id: c.parent_id,
          title: c.title,
          skip_numbering: c.skip_numbering,
          sort_order: c.sort_order,
        }))
      const steps = [...this.dirtySteps]
        .map((id) => this.stepMap.get(id))
        .filter((s): s is EditorStep => !!s)
        .map((s) => ({
          id: s.id,
          chapter_id: s.chapter_id,
          kind: s.kind,
          title: s.title,
          content: s.content,
          input_schema: s.input_schema,
          attachment_marks: s.attachment_marks,
          skip_numbering: s.skip_numbering,
          sort_order: s.sort_order,
        }))
      return {
        name: p.name,
        level_of_use: p.level_of_use,
        description: p.description,
        risk_level: p.risk_level,
        quality_level: p.quality_level,
        custom_values: p.custom_values,
        version_update_notes: p.version_update_notes,
        signoff_enabled: p.signoff_enabled,
        chapters,
        steps,
        deleted_chapter_ids: [...this.deletedChapterIds],
        deleted_step_ids: [...this.deletedStepIds],
      }
    },

    applyIdMap(idMap: Record<string, string>): void {
      const remap = (id: string | null): string | null => (id && idMap[id] ? idMap[id] : id)
      for (const c of this.chapters) {
        c.id = remap(c.id) as string
        c.parent_id = remap(c.parent_id)
      }
      for (const s of this.steps) {
        s.id = remap(s.id) as string
        s.chapter_id = remap(s.chapter_id)
      }
      const nextExpanded: Record<string, boolean> = {}
      for (const [k, v] of Object.entries(this.expanded)) nextExpanded[(idMap[k] ?? k) as string] = v
      this.expanded = nextExpanded
      this.selectedId = remap(this.selectedId)
    },

    async save(): Promise<Record<string, string>> {
      if (!this.procedure || !this.editable) return {}
      this.saving = true
      try {
        const result = await saveProcedure(this.procedure.id, this.buildPayload(), this.revision)
        this.applyIdMap(result.id_map)
        const { id_map: idMap, ...meta } = result
        this.procedure = meta as ProcedureMeta
        this.resetEditState()
        return idMap
      } finally {
        this.saving = false
      }
    },
  },
})
