import { computed, reactive, ref } from 'vue'
import type { ParseResponse } from '@/types/parse'
import type { ContentType, MarkStatus } from '@/types/node'
import {
  addChildNode,
  addSiblingNode,
  buildTreeFromRoles,
  buildWizardTree,
  cloneTree,
  computeChapterNumbers,
  computeLevelMap,
  computeMarkIndents,
  countReview,
  deleteNode,
  findNode,
  flattenForMarking,
  moveNode,
  restoreFromIgnored,
  setMarkStatus,
  updateNode,
  type LayerRole,
  type MarkRow,
  type WizardNode,
} from '@/utils/importTree'

export type ImportDialogMode = 'normal' | 'layer-marking' | 'step-annotation'

export function useImportDialog() {
  // ---- 文件 / 解析 ---- //
  const file = ref<File | null>(null)
  const uploadToken = ref('')
  const filename = ref('')
  const parseResult = ref<ParseResponse | null>(null)

  // ---- 树状态 ---- //
  const tree = ref<WizardNode[]>([])
  const ignored = ref<WizardNode[]>([])
  const selectedId = ref<string | null>(null)

  // ---- 模式 / 标记选择 ---- //
  const mode = ref<ImportDialogMode>('normal')
  const markSelection = ref<Set<string>>(new Set())

  // ---- 层级标定（平铺逐段） ---- //
  const roleMap = ref<Map<string, LayerRole>>(new Map())
  const markingBaseline = ref<WizardNode[] | null>(null)

  // ---- 表单 ---- //
  const form = reactive({ name: '', folder_id: '' })

  // ---- 派生 ---- //
  const selected = computed(() => (selectedId.value ? findNode(tree.value, selectedId.value) : null))
  const levelMap = computed(() => computeLevelMap(tree.value))
  const numberMap = computed(() => computeChapterNumbers(tree.value))
  const reviewCount = computed(() => countReview(tree.value))
  const markRows = computed<MarkRow[]>(() =>
    markingBaseline.value ? flattenForMarking(markingBaseline.value) : [],
  )
  const markIndents = computed(() => computeMarkIndents(markRows.value, roleMap.value))

  // ---- 模式切换 ---- //
  // 离开层级标定（任何方式：完成 / 再点按钮 / Esc / 切到步骤标注）统一以 baseline 为基准重建，
  // 改动总会保留；没有"丢弃"路径，整体反悔用「↺ 重置」。
  function applyAndClearMarking(): void {
    if (markingBaseline.value) {
      tree.value = buildTreeFromRoles(markingBaseline.value, roleMap.value)
    }
    roleMap.value = new Map()
    markingBaseline.value = null
  }

  function exitMode(): void {
    if (mode.value === 'layer-marking') applyAndClearMarking()
    mode.value = 'normal'
    markSelection.value = new Set()
  }

  function enterLayerMarking(): void {
    markingBaseline.value = cloneTree(tree.value)
    const m = new Map<string, LayerRole>()
    for (const r of flattenForMarking(markingBaseline.value)) m.set(r.id, r.defaultRole)
    roleMap.value = m
    mode.value = 'layer-marking'
    markSelection.value = new Set()
  }

  function toggleLayerMarking(): void {
    if (mode.value === 'layer-marking') exitMode()
    else enterLayerMarking()
  }

  function toggleStepAnnotation(): void {
    if (mode.value === 'step-annotation') {
      exitMode()
    } else {
      exitMode() // 若正处于层级标定，先统一生效再切换
      mode.value = 'step-annotation'
      markSelection.value = new Set()
    }
  }

  function setRole(id: string, role: LayerRole): void {
    const next = new Map(roleMap.value)
    next.set(id, role)
    roleMap.value = next
  }

  function toggleMarkSelection(id: string): void {
    const next = new Set(markSelection.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    markSelection.value = next
  }

  function clearMarkSelection(): void {
    markSelection.value = new Set()
  }

  // ---- 装载 / 树编辑 ---- //
  function loadParseResult(res: ParseResponse): void {
    parseResult.value = res
    tree.value = buildWizardTree(res.chapters)
    ignored.value = []
    selectedId.value = null
    mode.value = 'normal'
    markSelection.value = new Set()
    roleMap.value = new Map()
    markingBaseline.value = null
    if (!form.name) {
      form.name = filename.value.replace(/\.docx$/i, '').trim()
    }
  }

  function selectNode(id: string | null): void {
    selectedId.value = id
  }

  function moveSelected(dir: -1 | 1): void {
    if (!selectedId.value) return
    tree.value = moveNode(tree.value, selectedId.value, dir)
  }

  function deleteSelected(): void {
    if (!selectedId.value) return
    tree.value = deleteNode(tree.value, selectedId.value)
    selectedId.value = null
  }

  function addChild(parentId: string | null, type: ContentType): void {
    tree.value = addChildNode(tree.value, parentId, type)
  }

  function addSibling(siblingId: string, type: ContentType): void {
    tree.value = addSiblingNode(tree.value, siblingId, type)
  }

  function updateSelectedFields(patch: { title?: string; skip_numbering?: boolean; mark_status?: MarkStatus }): void {
    if (!selectedId.value) return
    tree.value = updateNode(tree.value, selectedId.value, patch)
  }

  // ---- 步骤标注动作 ---- //
  function applyStepAnnotation(role: 'step' | 'content'): void {
    const ids = [...markSelection.value]
    if (ids.length === 0) return
    tree.value = setMarkStatus(tree.value, ids, role)
    exitMode()
  }

  function clearStepAnnotation(): void {
    const ids = [...markSelection.value]
    if (ids.length === 0) return
    tree.value = setMarkStatus(tree.value, ids, 'unmarked')
    exitMode()
  }

  // ---- 忽略项恢复（保留：删除走普通模式永久删除，恢复机制不变） ---- //
  function restoreIgnored(id: string): void {
    const idx = ignored.value.findIndex((n) => n.id === id)
    if (idx === -1) return
    const node = ignored.value[idx]
    ignored.value = ignored.value.filter((_, i) => i !== idx)
    tree.value = restoreFromIgnored(tree.value, [node])
  }

  function restoreAllIgnored(): void {
    if (ignored.value.length === 0) return
    tree.value = restoreFromIgnored(tree.value, ignored.value)
    ignored.value = []
  }

  // ---- 接受 review ---- //
  function acceptReview(id: string): void {
    tree.value = updateNode(tree.value, id, { mark_status: 'unmarked' })
  }

  return {
    // state
    file, uploadToken, filename, parseResult,
    tree, ignored, selectedId, mode, markSelection, form,
    roleMap, markingBaseline,
    // derived
    selected, levelMap, numberMap, reviewCount, markRows, markIndents,
    // mode
    toggleLayerMarking, toggleStepAnnotation, exitMode,
    toggleMarkSelection, clearMarkSelection, setRole,
    // tree actions
    loadParseResult, selectNode, moveSelected, deleteSelected,
    addChild, addSibling, updateSelectedFields,
    // step annotation
    applyStepAnnotation, clearStepAnnotation,
    // ignored
    restoreIgnored, restoreAllIgnored,
    // review
    acceptReview,
  }
}
