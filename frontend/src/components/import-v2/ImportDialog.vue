<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import WordPreviewPanel from './WordPreviewPanel.vue'
import ImportTreePanel from './ImportTreePanel.vue'
import ImportDetailPanel from './ImportDetailPanel.vue'
import ImportSideRail from './ImportSideRail.vue'
import { useImportDialog } from '@/composables/useImportDialog'
import { importProcedure, parseDocx, uploadDocx } from '@/api/parse'
import { fetchFolderTree } from '@/api/folders'
import { toImportNodes } from '@/utils/importTree'
import type { LeafFolderOption } from '@/utils/folders'
import { collectLeafFolders } from '@/utils/folders'
import { useStorage, useEventListener } from '@vueuse/core'
import {
  COL_DEFAULTS,
  colFlex,
  resizeLeftMid,
  resizeMidRight,
  sanitizeCols,
  sanitizeCollapsed,
  type ColWidths,
  type CollapseState,
} from '@/utils/importCols'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'imported', procedureId: string): void
}>()

const ctx = useImportDialog()
const leaves = ref<LeafFolderOption[]>([])
const uploading = ref(false)
const parsing = ref(false)
const importing = ref(false)

const visible = computed<boolean>({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const colsRef = ref<HTMLDivElement | null>(null)
const cols = useStorage<ColWidths>('smartsop.import.cols', { ...COL_DEFAULTS })
// Guard against dirty/legacy persisted values on load.
cols.value = sanitizeCols(cols.value)

const collapsed = useStorage<CollapseState>('smartsop.import.collapsed', { left: false, right: false })
// 守卫脏值/旧值
collapsed.value = sanitizeCollapsed(collapsed.value)

const cf = computed(() => colFlex(cols.value, collapsed.value))

type Handle = 'lm' | 'mr'
const drag = ref<{ handle: Handle; startX: number; start: ColWidths; containerW: number } | null>(null)

function onDragStart(e: PointerEvent, handle: Handle): void {
  if (!colsRef.value) return
  e.preventDefault()
  // Capture the pointer so releasing outside the window still ends the drag cleanly.
  const target = e.currentTarget as HTMLElement
  target.setPointerCapture(e.pointerId)
  drag.value = {
    handle,
    startX: e.clientX,
    start: { ...cols.value },
    containerW: colsRef.value.getBoundingClientRect().width,
  }
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
}

function endDrag(): void {
  if (!drag.value) return
  drag.value = null
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
}

function resetCols(): void {
  cols.value = { ...COL_DEFAULTS }
}

useEventListener(window, 'pointermove', (e: PointerEvent) => {
  const d = drag.value
  if (!d || d.containerW === 0) return
  const deltaPct = ((e.clientX - d.startX) / d.containerW) * 100
  cols.value = d.handle === 'lm' ? resizeLeftMid(d.start, deltaPct) : resizeMidRight(d.start, deltaPct)
})

useEventListener(window, 'pointerup', endDrag)
useEventListener(window, 'pointercancel', endDrag)

onMounted(async () => {
  try {
    leaves.value = collectLeafFolders(await fetchFolderTree())
  } catch { /* api interceptor will show error */ }
})

async function onPickFile(f: File): Promise<void> {
  ctx.file.value = f
  ctx.filename.value = f.name
  uploading.value = true
  try {
    const up = await uploadDocx(f)
    ctx.uploadToken.value = up.upload_token
    parsing.value = true
    const res = await parseDocx(up.upload_token, 'smart')
    ctx.loadParseResult(res)
  } catch { /* api interceptor shows error */ }
  finally {
    uploading.value = false
    parsing.value = false
  }
}

async function onSubmit(): Promise<void> {
  if (!ctx.form.name.trim()) { ElMessage.warning('请输入程序名称'); return }
  if (!ctx.form.folder_id) { ElMessage.warning('请选择目标文件夹'); return }
  if (ctx.reviewCount.value > 0) {
    try {
      await ElMessageBox.confirm(
        `仍有 ${ctx.reviewCount.value} 个待确认节点，确认导入将自动接受全部？`,
        '存在待确认',
        { type: 'warning' },
      )
    } catch { return }
  }
  importing.value = true
  try {
    const proc = await importProcedure({
      name: ctx.form.name.trim(),
      folder_id: ctx.form.folder_id,
      description: '',
      upload_token: ctx.uploadToken.value,
      chapters: toImportNodes(ctx.tree.value),
    })
    ElMessage.success(`已导入 ${proc.code}`)
    visible.value = false
    emit('imported', proc.id)
  } catch { /* interceptor */ }
  finally { importing.value = false }
}

function onCloseRequest(): void {
  if (ctx.tree.value.length > 0) {
    ElMessageBox.confirm('放弃当前进度并关闭？', '关闭确认', { type: 'warning' })
      .then(() => { visible.value = false })
      .catch(() => {})
  } else { visible.value = false }
}

function onFileInput(e: Event): void {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) void onPickFile(f)
}

function onKey(ev: KeyboardEvent): void {
  if (!visible.value) return
  const tgt = ev.target as HTMLElement
  // 输入框中不拦截
  if (['INPUT', 'TEXTAREA'].includes(tgt.tagName) || tgt.isContentEditable) {
    if (ev.key === 'Escape' && ctx.mode.value !== 'normal') {
      ctx.exitMode()
      ev.preventDefault()
    }
    return
  }
  if (ev.key === 'Escape') {
    if (ctx.mode.value !== 'normal') {
      ctx.exitMode()
      ev.preventDefault()
      return
    }
    onCloseRequest()
    ev.preventDefault()
    return
  }
  if (ev.key === 'Delete' && ctx.selectedId.value) {
    ctx.deleteSelected()
    ev.preventDefault()
    return
  }
}

watch(visible, (on) => {
  if (on) window.addEventListener('keydown', onKey)
  else window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <el-dialog
    v-model="visible"
    width="96vw"
    top="3vh"
    :show-close="false"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    align-center
    class="import-dialog"
  >
    <template #header>
      <div class="hdr">
        <el-button text @click="onCloseRequest">✕</el-button>
        <span class="title">从 Word 导入</span>
        <span v-if="ctx.filename.value" class="fname">· {{ ctx.filename.value }}</span>
        <el-tag v-if="ctx.reviewCount.value > 0" type="warning" effect="plain" disable-transitions>
          ⚠ {{ ctx.reviewCount.value }} 个待确认
        </el-tag>
        <span class="spacer" />
        <el-input v-model="ctx.form.name" size="small" placeholder="程序名称" style="width: 180px" />
        <el-select v-model="ctx.form.folder_id" size="small" filterable placeholder="目标文件夹" style="width: 200px">
          <el-option v-for="leaf in leaves" :key="leaf.id" :label="leaf.label" :value="leaf.id" />
        </el-select>
        <el-button type="primary" :loading="importing" :disabled="!ctx.tree.value.length" @click="onSubmit">
          提交导入
        </el-button>
      </div>
    </template>

    <div class="body" :style="{ height: '88vh' }">
      <div v-if="!ctx.parseResult.value" class="upload-stage">
        <div class="upload-card">
          <h3>选择 Word 文件开始</h3>
          <input type="file" accept=".docx" @change="onFileInput" />
          <div v-if="uploading" class="hint">上传中...</div>
          <div v-if="parsing" class="hint">解析中...</div>
        </div>
      </div>
      <div v-else ref="colsRef" class="cols">
        <div class="col" :style="{ flex: cf.left }">
          <ImportSideRail
            v-if="collapsed.left"
            label="Word 原文预览"
            side="left"
            @expand="collapsed.left = false"
          />
          <WordPreviewPanel v-else :file="ctx.file.value" />
        </div>
        <div
          v-if="cf.showLM"
          class="splitter"
          title="拖拽调整列宽，双击重置"
          @pointerdown="onDragStart($event, 'lm')"
          @dblclick="resetCols"
        >
          <button
            class="collapse-btn"
            title="折叠原文预览"
            @click.stop="collapsed.left = true"
            @pointerdown.stop
          >«</button>
        </div>
        <div class="col" :style="{ flex: cf.mid }"><ImportTreePanel :ctx="ctx" /></div>
        <div
          v-if="cf.showMR"
          class="splitter"
          title="拖拽调整列宽，双击重置"
          @pointerdown="onDragStart($event, 'mr')"
          @dblclick="resetCols"
        >
          <button
            class="collapse-btn"
            title="折叠详情"
            @click.stop="collapsed.right = true"
            @pointerdown.stop
          >»</button>
        </div>
        <div class="col" :style="{ flex: cf.right }">
          <ImportSideRail
            v-if="collapsed.right"
            label="详情"
            side="right"
            @expand="collapsed.right = false"
          />
          <ImportDetailPanel v-else :ctx="ctx" />
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.import-dialog :deep(.el-dialog__header) { padding: 0; margin: 0; border-bottom: 1px solid var(--el-border-color-lighter, #ebeef5); }
.import-dialog :deep(.el-dialog__body) { padding: 0; }
.hdr { display: flex; align-items: center; gap: 12px; padding: 10px 14px; }
.title { font-weight: 600; font-size: 15px; }
.fname { color: #909399; font-size: 13px; }
.spacer { flex: 1; }
.body { display: flex; flex-direction: column; }
.upload-stage { flex: 1; display: flex; align-items: center; justify-content: center; padding: 40px; }
.upload-card { padding: 32px 48px; background: #f5f7fa; border-radius: 8px; text-align: center; }
.upload-card input { margin-top: 12px; }
.hint { margin-top: 8px; color: #606266; }
.cols { flex: 1; display: flex; min-height: 0; }
.col { display: flex; flex-direction: column; min-width: 0; }
.splitter {
  flex: none;
  width: 6px;
  cursor: col-resize;
  position: relative;
  z-index: 1;
  touch-action: none;
}
.splitter::after {
  content: '';
  position: absolute;
  inset: 0 2px;
  background: transparent;
  transition: background 0.15s;
}
.splitter:hover::after { background: var(--el-color-primary, #d97757); }
.collapse-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  width: 18px;
  height: 36px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  background: #fff;
  color: #909399;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, border-color 0.15s;
}
.splitter:hover .collapse-btn { opacity: 1; }
.collapse-btn:hover { color: var(--el-color-primary, #d97757); border-color: var(--el-color-primary, #d97757); }
</style>
