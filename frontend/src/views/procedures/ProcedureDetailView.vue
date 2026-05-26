<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import StatusTag from '@/components/StatusTag.vue'
import VersionListPanel from '@/components/version/VersionListPanel.vue'
import VersionActionDialog, {
  type VersionActionResult,
} from '@/components/version/VersionActionDialog.vue'
import PdfPreviewDialog from '@/components/PdfPreview/PdfPreviewDialog.vue'
import {
  archiveGroup,
  copyProcedure,
  deleteGroup,
  deleteProcedure,
  deprecateGroup,
  downloadPdf,
  fetchProcedureDetail,
  restoreGroup,
  restorePreview,
  rollbackVersion,
  transitionProcedure,
  updateProcedure,
  upgradeVersion,
} from '@/api/procedures'
import { LEVEL_OF_USE_LABELS, formatDateTime } from '@/utils/format'
import type { LevelOfUse, ProcedureMeta } from '@/types/procedure'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const meta = ref<ProcedureMeta | null>(null)
const loading = ref(false)
const editVisible = ref(false)
const busy = ref(false)
const panelRef = ref<InstanceType<typeof VersionListPanel> | null>(null)
// PDF 预览 / 下载（任意 is_current=true 程序可用，editor-behavior §10）
const previewVisible = ref(false)
const pdfBusy = ref(false)
const canPdf = computed(() => !!meta.value?.is_current)

async function onDownloadPdf(): Promise<void> {
  pdfBusy.value = true
  try {
    await downloadPdf(id.value)
  } catch {
    /* 拦截器已提示 */
  } finally {
    pdfBusy.value = false
  }
}

const editable = computed(
  () => !!meta.value && meta.value.is_current && meta.value.status === 'DRAFT' && !deprecated.value,
)
const deprecated = computed(() => !!meta.value?.deprecated_at)
const canUpgrade = computed(
  () => !!meta.value && meta.value.is_current && meta.value.status === 'PUBLISHED' && !deprecated.value,
)
const canArchive = computed(
  () =>
    !!meta.value &&
    meta.value.is_current &&
    meta.value.status === 'PUBLISHED' &&
    !deprecated.value,
)
// 删除可见性（对齐后端 delete_procedure）：非当前版可软删；当前版仅 DRAFT 可删
//（v1→整组硬删，v>1→丢弃草稿）；当前 PUBLISHED/ARCHIVED 一律不可直接删。
const canDelete = computed(() => {
  const m = meta.value
  if (!m) return false
  if (!m.is_current) return true
  return m.status === 'DRAFT'
})

// ---- 头部「本次版本更新说明」（DRAFT 可改，其余只读，Q356） ---- //
const notesDraft = ref('')
const notesDirty = computed(() => !!meta.value && notesDraft.value !== meta.value.version_update_notes)

interface EditForm {
  name: string
  level_of_use: LevelOfUse
  description: string
  risk_level: number
  quality_level: number
  version_update_notes: string
}
const form = reactive<EditForm>({
  name: '',
  level_of_use: 'continuous',
  description: '',
  risk_level: 1,
  quality_level: 1,
  version_update_notes: '',
})

async function load(): Promise<void> {
  loading.value = true
  try {
    const detail = await fetchProcedureDetail(id.value)
    meta.value = detail.procedure
    notesDraft.value = detail.procedure.version_update_notes
  } finally {
    loading.value = false
  }
}
onMounted(load)

function metaUpdatePayload(overrides: Partial<EditForm> = {}) {
  const m = meta.value!
  return {
    name: m.name,
    level_of_use: m.level_of_use,
    description: m.description,
    risk_level: m.risk_level,
    quality_level: m.quality_level,
    version_update_notes: m.version_update_notes,
    ...overrides,
  }
}

async function saveNotes(): Promise<void> {
  if (!meta.value || !notesDirty.value) return
  busy.value = true
  try {
    await updateProcedure(id.value, metaUpdatePayload({ version_update_notes: notesDraft.value }), meta.value.revision)
    ElMessage.success('已保存更新说明')
    await load()
  } catch {
    /* 拦截器已提示 */
  } finally {
    busy.value = false
  }
}

function openEdit(): void {
  if (!meta.value) return
  Object.assign(form, {
    name: meta.value.name,
    level_of_use: meta.value.level_of_use,
    description: meta.value.description,
    risk_level: meta.value.risk_level,
    quality_level: meta.value.quality_level,
    version_update_notes: meta.value.version_update_notes,
  })
  editVisible.value = true
}

async function saveEdit(): Promise<void> {
  if (!meta.value) return
  busy.value = true
  try {
    await updateProcedure(id.value, { ...form }, meta.value.revision)
    ElMessage.success('已保存')
    editVisible.value = false
    await load()
  } catch {
    /* 拦截器已提示 */
  } finally {
    busy.value = false
  }
}

async function doTransition(status: 'PUBLISHED' | 'ARCHIVED', label: string): Promise<void> {
  if (!meta.value) return
  try {
    await ElMessageBox.confirm(`确定${label}此程序？`, `${label}确认`, { type: 'warning' })
  } catch {
    return // 用户取消
  }
  busy.value = true
  try {
    await transitionProcedure(id.value, { status }, meta.value.revision)
    ElMessage.success(`已${label}`)
    await load()
  } catch {
    /* 拦截器已提示 */
  } finally {
    busy.value = false
  }
}

async function remove(): Promise<void> {
  const m = meta.value
  if (!m) return
  let reason: string
  try {
    const r = await ElMessageBox.prompt('请输入删除原因', '删除确认', {
      inputValidator: (v) => (v && v.trim() ? true : '删除原因必填'),
      type: 'warning',
    })
    reason = r.value
  } catch {
    return // 用户取消
  }
  busy.value = true
  try {
    // v1 草稿当前版 → 整组硬删（§22.13）；其余走 deleteProcedure（丢弃草稿 / 软删非当前版）。
    if (m.is_current && m.status === 'DRAFT' && m.version === 1) {
      await deleteGroup(m.procedure_group_id, reason)
      ElMessage.success('已删除')
      void router.push('/procedures/library')
      return
    }
    const result = await deleteProcedure(id.value, reason)
    if (result) {
      // 丢弃 DRAFT（v>1 当前版）→ 跳转到新当前版（§22.11）。
      ElMessage.success(`已丢弃草稿，当前版本回到 v${result.new_current_version}`)
      void router.push(`/procedures/${result.new_current_id}`)
    } else {
      ElMessage.success('已删除')
      void router.push('/procedures/library')
    }
  } catch {
    /* 拦截器已提示 */
  } finally {
    busy.value = false
  }
}

async function onUpgrade(): Promise<void> {
  if (!meta.value) return
  await ElMessageBox.confirm('升级将归档当前版本并创建新草稿版本，是否继续？', '升级版本', {
    type: 'warning',
  })
  busy.value = true
  try {
    const next = await upgradeVersion(meta.value.id)
    ElMessage.success(`已创建 v${next.version} 草稿`)
    void router.push(`/procedures/${next.id}/edit`)
  } finally {
    busy.value = false
  }
}

// ---- 版本动作统一弹框 ---- //
type PendingAction =
  | { kind: 'deprecate' }
  | { kind: 'archive' }
  | { kind: 'restore'; needFolder: boolean }
  | { kind: 'copy' }
  | { kind: 'rollback'; currentId: string; targetVersion: number }

const dialogVisible = ref(false)
const pending = ref<PendingAction | null>(null)

const dialogConfig = computed(() => {
  const p = pending.value
  if (p?.kind === 'deprecate') {
    return { title: '废弃整个版本族', needReason: true, needFolder: false, needName: false, reasonHint: '废弃原因（整组所有版本将移入「废止」）' }
  }
  if (p?.kind === 'archive') {
    return { title: '归档整个版本族', needReason: true, needFolder: false, needName: false, reasonHint: '归档原因（整组所有版本将移入「归档」，保留备查）' }
  }
  if (p?.kind === 'restore') {
    return { title: '从废止恢复', needReason: true, needFolder: p.needFolder, needName: false, reasonHint: '恢复原因' }
  }
  if (p?.kind === 'copy') {
    return { title: '复制为新程序', needReason: false, needFolder: true, needName: true, reasonHint: '' }
  }
  if (p?.kind === 'rollback') {
    return { title: `回退到 v${p.targetVersion}`, needReason: true, needFolder: false, needName: false, reasonHint: '回退原因' }
  }
  return { title: '', needReason: false, needFolder: false, needName: false, reasonHint: '' }
})

function openDeprecate(): void {
  pending.value = { kind: 'deprecate' }
  dialogVisible.value = true
}
function openArchive(): void {
  pending.value = { kind: 'archive' }
  dialogVisible.value = true
}
async function openRestore(): Promise<void> {
  if (!meta.value) return
  busy.value = true
  try {
    const preview = await restorePreview(meta.value.id)
    pending.value = { kind: 'restore', needFolder: !preview.folder_exists }
    dialogVisible.value = true
  } catch {
    /* 拦截器已提示 */
  } finally {
    busy.value = false
  }
}
function openCopy(): void {
  pending.value = { kind: 'copy' }
  dialogVisible.value = true
}
function onRollback(targetVersion: number, currentId: string): void {
  pending.value = { kind: 'rollback', currentId, targetVersion }
  dialogVisible.value = true
}

async function onDialogConfirm(payload: VersionActionResult): Promise<void> {
  const p = pending.value
  if (!p || !meta.value) return
  busy.value = true
  try {
    if (p.kind === 'deprecate') {
      await deprecateGroup(meta.value.id, payload.reason)
      dialogVisible.value = false
      ElMessage.success('已废弃整个版本族')
      await load()
      panelRef.value?.reload()
    } else if (p.kind === 'archive') {
      await archiveGroup(meta.value.id, payload.reason)
      dialogVisible.value = false
      ElMessage.success('已归档整版本族')
      await load()
      panelRef.value?.reload()
    } else if (p.kind === 'restore') {
      const next = await restoreGroup(meta.value.id, {
        reason: payload.reason,
        target_folder_id: payload.target_folder_id || undefined,
      })
      dialogVisible.value = false
      ElMessage.success(`已恢复并创建 v${next.version} 草稿`)
      void router.push(`/procedures/${next.id}/edit`)
    } else if (p.kind === 'copy') {
      const copy = await copyProcedure(meta.value.id, {
        target_folder_id: payload.target_folder_id,
        name: payload.name || undefined,
      })
      dialogVisible.value = false
      ElMessage.success(`已复制为 ${copy.code}`)
      void router.push(`/procedures/${copy.id}/edit`)
    } else {
      const next = await rollbackVersion(p.currentId, {
        target_version: p.targetVersion,
        reason: payload.reason,
      })
      dialogVisible.value = false
      ElMessage.success(`已回退并创建 v${next.version} 草稿`)
      void router.push(`/procedures/${next.id}/edit`)
    }
  } catch {
    /* 拦截器已提示 */
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-loading="loading" class="detail">
    <template v-if="meta">
      <div class="header">
        <div>
          <h2 class="title">{{ meta.code }} · {{ meta.name }}</h2>
          <div class="sub">
            <StatusTag :status="meta.status" />
            <span class="ver">v{{ meta.version }}</span>
            <el-tag v-if="deprecated" size="small" type="danger" disable-transitions>已废止</el-tag>
            <span class="path">{{ meta.folder_full_path }}</span>
          </div>
        </div>
        <div class="actions">
          <el-button
            type="primary"
            plain
            @click="router.push({ name: editable ? 'procedure-edit' : 'procedure-view', params: { id } })"
          >
            {{ editable ? '进入编辑器' : '查看内容' }}
          </el-button>
          <el-button v-if="editable" @click="openEdit">快速编辑</el-button>
          <el-button v-if="editable" type="primary" @click="doTransition('PUBLISHED', '发布')">
            发布
          </el-button>
          <el-button v-if="canPdf" @click="previewVisible = true">PDF 预览</el-button>
          <el-button v-if="canPdf" :loading="pdfBusy" @click="onDownloadPdf">PDF 下载</el-button>
          <el-button v-if="canUpgrade" type="primary" plain :disabled="busy" @click="onUpgrade">
            升级版本
          </el-button>
          <el-button v-if="canUpgrade" type="warning" @click="doTransition('ARCHIVED', '归档')">
            归档
          </el-button>
          <el-button :disabled="busy" @click="openCopy">复制为新程序</el-button>
          <el-button v-if="!deprecated" type="warning" plain :disabled="busy" @click="openDeprecate">
            废弃
          </el-button>
          <el-button v-if="canArchive" type="warning" link :disabled="busy" @click="openArchive">
            归档整版本族
          </el-button>
          <el-button v-if="deprecated" type="success" plain :disabled="busy" @click="openRestore">
            恢复
          </el-button>
          <el-button v-if="canDelete" type="danger" plain :disabled="busy" @click="remove">
            删除
          </el-button>
        </div>
      </div>

      <el-alert
        v-if="deprecated"
        type="error"
        :closable="false"
        show-icon
        class="ro-banner"
        title="该版本族已废止：仅可恢复或复制；编辑 / 发布 / 升级均被禁用。"
      />
      <el-alert
        v-else-if="!editable"
        type="info"
        :closable="false"
        show-icon
        class="ro-banner"
        title="只读：仅当前版本的草稿可编辑。"
      />

      <el-descriptions :column="2" border class="meta">
        <el-descriptions-item label="用途级别">
          {{ LEVEL_OF_USE_LABELS[meta.level_of_use] ?? meta.level_of_use }}
        </el-descriptions-item>
        <el-descriptions-item label="是否当前版本">{{ meta.is_current ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="风险等级">{{ meta.risk_level }}</el-descriptions-item>
        <el-descriptions-item label="质量等级">{{ meta.quality_level }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(meta.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatDateTime(meta.updated_at) }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ meta.description || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-card shadow="never" class="notes-card">
        <template #header>
          <div class="notes-hd">
            <span>本次版本更新说明</span>
            <el-button
              v-if="editable && notesDirty"
              size="small"
              type="primary"
              :loading="busy"
              @click="saveNotes"
            >
              保存说明
            </el-button>
          </div>
        </template>
        <el-input
          v-if="editable"
          v-model="notesDraft"
          type="textarea"
          :rows="3"
          maxlength="10000"
          placeholder="填写本次版本相对上一版的变更说明（将写入 PDF 修订记录页）"
        />
        <p v-else class="notes-ro">{{ meta.version_update_notes || '（无更新说明）' }}</p>
      </el-card>

      <VersionListPanel
        ref="panelRef"
        :group-id="meta.procedure_group_id"
        :viewing-id="meta.id"
        @view="(vid) => router.push(`/procedures/${vid}`)"
        @rollback="onRollback"
      />

      <el-card shadow="never" class="vlog">
        <template #header>版本变更日志（本版）</template>
        <el-timeline v-if="meta.version_change_log.length">
          <el-timeline-item
            v-for="(entry, idx) in meta.version_change_log"
            :key="idx"
            :timestamp="formatDateTime(String(entry.changed_at ?? ''))"
          >
            {{ entry.change_type }} — {{ entry.description || '' }}
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无记录" />
      </el-card>

      <el-dialog v-model="editVisible" title="编辑程序" width="520px">
        <el-form label-width="120px">
          <el-form-item label="名称" required>
            <el-input v-model="form.name" maxlength="200" />
          </el-form-item>
          <el-form-item label="用途级别" required>
            <el-select v-model="form.level_of_use" class="full">
              <el-option label="参考 (reference)" value="reference" />
              <el-option label="连续使用 (continuous)" value="continuous" />
              <el-option label="信息 (information)" value="information" />
            </el-select>
          </el-form-item>
          <el-form-item label="风险等级">
            <el-input-number v-model="form.risk_level" :min="1" :max="5" />
          </el-form-item>
          <el-form-item label="质量等级">
            <el-input-number v-model="form.quality_level" :min="1" :max="5" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model="form.description" type="textarea" :rows="3" maxlength="10000" />
          </el-form-item>
          <el-form-item label="本次版本更新说明">
            <el-input v-model="form.version_update_notes" type="textarea" :rows="2" maxlength="10000" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="editVisible = false">取消</el-button>
          <el-button type="primary" :loading="busy" @click="saveEdit">保存</el-button>
        </template>
      </el-dialog>

      <VersionActionDialog
        v-model="dialogVisible"
        :title="dialogConfig.title"
        :need-reason="dialogConfig.needReason"
        :need-folder="dialogConfig.needFolder"
        :need-name="dialogConfig.needName"
        :reason-hint="dialogConfig.reasonHint"
        :loading="busy"
        @confirm="onDialogConfirm"
      />

      <PdfPreviewDialog v-model="previewVisible" :procedure-id="id" />
    </template>
  </div>
</template>

<style scoped>
.detail {
  padding: 20px 24px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 16px;
}
.title {
  margin: 0 0 8px;
  font-size: 20px;
}
.sub {
  display: flex;
  align-items: center;
  gap: 14px;
  color: #666;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}
.ro-banner {
  margin-bottom: 16px;
}
.meta {
  margin-bottom: 20px;
}
.notes-card {
  margin-bottom: 20px;
}
.notes-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.notes-ro {
  margin: 0;
  color: #606266;
  white-space: pre-wrap;
}
.full {
  width: 100%;
}
</style>
