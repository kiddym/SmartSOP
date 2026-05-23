<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import WordPreviewPanel from './WordPreviewPanel.vue'
import ImportTreePanel from './ImportTreePanel.vue'
import ImportDetailPanel from './ImportDetailPanel.vue'
import { useImportDialog } from '@/composables/useImportDialog'
import { importProcedure, parseDocx, uploadDocx } from '@/api/parse'
import { fetchFolderTree } from '@/api/folders'
import { toImportNodes } from '@/utils/importTree'
import type { LeafFolderOption } from '@/utils/folders'
import { collectLeafFolders } from '@/utils/folders'

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
  if (ev.key === 'Tab' && ctx.selectedId.value) {
    if (ev.shiftKey) ctx.promoteSelected()
    else ctx.demoteSelected()
    ev.preventDefault()
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
      <div v-else class="cols">
        <div class="col left"><WordPreviewPanel :file="ctx.file.value" /></div>
        <div class="col mid"><ImportTreePanel :ctx="ctx" /></div>
        <div class="col right"><ImportDetailPanel :ctx="ctx" /></div>
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
.col.left { width: 28%; }
.col.mid { width: 37%; }
.col.right { width: 35%; }
</style>
