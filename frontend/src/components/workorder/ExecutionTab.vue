<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import { getExecution, patchStepResult } from '@/api/workOrders'
import { listEntityAttachments, uploadEntityAttachment, deleteAttachment } from '@/api/attachments'
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/store/auth'
import type { ExecutionView, StepResultRead, StepResultUpdate } from '@/types/workOrder'
import type { AttachmentOut } from '@/types/attachment'
import type { UserRead } from '@/types/platform'
import { formatDateTime } from '@/utils/format'
import SignaturePad from '@/components/workorder/SignaturePad.vue'

const props = defineProps<{ workOrderId: string }>()

const auth = useAuthStore()
const canExecute = computed(() => auth.hasPermission('work_order.execute'))

const exec = ref<ExecutionView | null>(null)
const users = ref<UserRead[]>([])
const loading = ref(false)
// 每步独立保存中标志，按 result id 记录。
const saving = reactive<Record<string, boolean>>({})

// 本地可编辑草稿，按 result id 缓存 { value, values, notes }，初值来自 result。
interface Draft {
  value: string | number | boolean | null
  values: string[]
  notes: string
}
const drafts = reactive<Record<string, Draft>>({})

function userName(id: string | null): string {
  if (!id) return '—'
  const found = users.value.find((u) => u.id === id)
  return found ? found.name : '—'
}

function stepType(step: StepResultRead): string {
  const t = step.input_schema?.type
  return typeof t === 'string' ? t.toUpperCase() : 'COMMON'
}

// 录入型（有独立控件）才需要 value/values；其余仅 done/notes。
const VALUE_TYPES = new Set([
  'CHECK',
  'YESNO',
  'NUMBER',
  'METER',
  'CHECKBOX',
  'RADIO',
  'DATE',
])
function hasInput(step: StepResultRead): boolean {
  return VALUE_TYPES.has(stepType(step))
}
function isMulti(step: StepResultRead): boolean {
  return stepType(step) === 'CHECKBOX'
}

// 附件类型步骤：UPLOAD / PHOTO / SIGNATURE（SIGNATURE 控件 Task 7 加，加载逻辑本 Task 覆盖）。
const ATTACHMENT_TYPES = new Set(['UPLOAD', 'PHOTO', 'SIGNATURE'])
function isAttachmentType(step: StepResultRead): boolean {
  return ATTACHMENT_TYPES.has(stepType(step))
}

// 按 step id 缓存附件列表。
const stepAttachments = reactive<Record<string, AttachmentOut[]>>({})

async function loadStepAttachments(stepId: string): Promise<void> {
  stepAttachments[stepId] = await listEntityAttachments('work_order_step_result', stepId)
}

async function onUpload(stepId: string, file: File): Promise<void> {
  await uploadEntityAttachment('work_order_step_result', stepId, file)
  await loadStepAttachments(stepId)
}

/** 供 el-upload :http-request 绑定；接收 UploadRequestOptions，取出 file 后转给 onUpload。 */
function handleUploadRequest(stepId: string): (opt: UploadRequestOptions) => Promise<void> {
  return (opt: UploadRequestOptions) => onUpload(stepId, opt.file)
}

async function onRemoveAttachment(stepId: string, attId: string): Promise<void> {
  await deleteAttachment(attId)
  await loadStepAttachments(stepId)
}

function schemaStr(step: StepResultRead, key: string, fallback = ''): string {
  const v = step.input_schema?.[key]
  return typeof v === 'string' && v !== '' ? v : fallback
}
function schemaOptions(step: StepResultRead): string[] {
  const v = step.input_schema?.options
  return Array.isArray(v) ? v.map((x) => String(x)) : []
}

function seedDraft(step: StepResultRead): void {
  const resp = step.response ?? {}
  const rawValues = resp.values
  drafts[step.id] = {
    value: (resp.value as Draft['value']) ?? null,
    values: Array.isArray(rawValues) ? rawValues.map((x) => String(x)) : [],
    notes: step.notes ?? '',
  }
}

function buildResponse(step: StepResultRead): Record<string, unknown> {
  if (!hasInput(step)) return step.response ?? {}
  const d = drafts[step.id]
  return isMulti(step) ? { values: d.values } : { value: d.value }
}

async function applyView(view: ExecutionView): Promise<void> {
  exec.value = view
  for (const s of view.steps) {
    seedDraft(s)
  }
  await Promise.all(
    view.steps.filter(isAttachmentType).map((s) => loadStepAttachments(s.id)),
  )
}

onMounted(async () => {
  loading.value = true
  try {
    const [u, e] = await Promise.all([listUsers(), getExecution(props.workOrderId)])
    users.value = u
    await applyView(e)
  } catch {
    ElMessage.error('加载执行视图失败，请重试')
  } finally {
    loading.value = false
  }
})

async function save(step: StepResultRead, markDone: boolean | null): Promise<void> {
  const d = drafts[step.id]
  const payload: StepResultUpdate = { notes: d.notes }
  if (hasInput(step)) payload.response = buildResponse(step)
  if (markDone !== null) payload.is_done = markDone
  saving[step.id] = true
  try {
    const view = await patchStepResult(props.workOrderId, step.id, payload)
    await applyView(view)
    ElMessage.success(markDone === true ? '步骤已标记完成' : '已保存')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    saving[step.id] = false
  }
}

defineExpose({ exec, drafts, save, canExecute })
</script>

<template>
  <div v-loading="loading" class="execution-tab">
    <template v-if="exec?.procedure">
      <div class="procedure-header">
        <span class="procedure-code">{{ exec.procedure.code }}</span>
        <span class="procedure-name">{{ exec.procedure.name }}</span>
        <el-tag size="small" type="info">v{{ exec.procedure.version }}</el-tag>
      </div>
    </template>

    <el-empty v-if="!exec?.steps?.length" description="未挂接 SOP 或无执行步骤" />

    <div v-else class="steps-list">
      <div v-for="step in exec.steps" :key="step.id" class="step-row" :data-step="step.node_code">
        <div class="step-head">
          <span class="step-code">{{ step.node_code }}</span>
          <el-tag size="small" :type="step.is_done ? 'success' : 'info'">
            {{ step.is_done ? '已完成' : '未完成' }}
          </el-tag>
          <span v-if="step.is_done" class="step-done-meta">
            {{ userName(step.done_by_user_id) }} · {{ formatDateTime(step.done_at) }}
          </span>
        </div>

        <div class="step-body">
          <!-- 录入控件按 input_schema.type 分发 -->
          <template v-if="canExecute">
            <el-input
              v-if="stepType(step) === 'NUMBER' || stepType(step) === 'METER'"
              v-model="drafts[step.id].value"
              type="number"
              class="step-input"
              :placeholder="stepType(step) === 'METER' ? schemaStr(step, 'name', '读数') : '数值'"
            >
              <template v-if="schemaStr(step, 'unit')" #append>{{ schemaStr(step, 'unit') }}</template>
            </el-input>

            <el-switch
              v-else-if="stepType(step) === 'CHECK'"
              v-model="drafts[step.id].value"
              :active-text="schemaStr(step, 'pass_label', '通过')"
              :inactive-text="schemaStr(step, 'fail_label', '不通过')"
            />

            <el-switch
              v-else-if="stepType(step) === 'YESNO'"
              v-model="drafts[step.id].value"
              :active-text="schemaStr(step, 'yes_label', '是')"
              :inactive-text="schemaStr(step, 'no_label', '否')"
            />

            <el-select
              v-else-if="stepType(step) === 'RADIO'"
              v-model="drafts[step.id].value"
              class="step-input"
              placeholder="请选择"
            >
              <el-option v-for="(opt, i) in schemaOptions(step)" :key="i" :label="opt" :value="opt" />
            </el-select>

            <el-checkbox-group
              v-else-if="stepType(step) === 'CHECKBOX'"
              v-model="drafts[step.id].values"
            >
              <el-checkbox v-for="(opt, i) in schemaOptions(step)" :key="i" :value="opt">
                {{ opt }}
              </el-checkbox>
            </el-checkbox-group>

            <el-date-picker
              v-else-if="stepType(step) === 'DATE'"
              v-model="drafts[step.id].value"
              class="step-input"
              :type="step.input_schema?.with_time ? 'datetime' : 'date'"
              placeholder="选择日期"
            />

            <template v-else-if="stepType(step) === 'UPLOAD' || stepType(step) === 'PHOTO'">
              <el-upload
                :show-file-list="false"
                :accept="stepType(step) === 'PHOTO' ? 'image/*' : undefined"
                :http-request="handleUploadRequest(step.id)"
              >
                <el-button size="small">上传文件</el-button>
              </el-upload>
              <ul class="att-list">
                <li v-for="a in stepAttachments[step.id] || []" :key="a.id">
                  {{ a.file_name }}
                  <el-button link type="danger" size="small" @click="onRemoveAttachment(step.id, a.id)">删除</el-button>
                </li>
              </ul>
            </template>

            <template v-else-if="stepType(step) === 'SIGNATURE'">
              <SignaturePad @confirm="(f) => onUpload(step.id, f)" />
              <ul class="att-list">
                <li v-for="a in stepAttachments[step.id] || []" :key="a.id">
                  {{ a.file_name }}
                  <el-button link type="danger" size="small" @click="onRemoveAttachment(step.id, a.id)">删除</el-button>
                </li>
              </ul>
            </template>

            <span v-else class="step-hint">本步骤无录入项，确认后勾选完成。</span>

            <el-input
              v-model="drafts[step.id].notes"
              class="step-notes"
              type="textarea"
              :rows="1"
              placeholder="备注（可选）"
            />

            <div class="step-actions">
              <el-button size="small" :loading="saving[step.id]" @click="save(step, null)">
                保存
              </el-button>
              <el-button
                v-if="!step.is_done"
                size="small"
                type="primary"
                :loading="saving[step.id]"
                @click="save(step, true)"
              >
                标记完成
              </el-button>
              <el-button
                v-else
                size="small"
                :loading="saving[step.id]"
                @click="save(step, false)"
              >
                取消完成
              </el-button>
            </div>
          </template>

          <!-- 只读态（无 work_order.execute 权限）：保持原有展示，附件类型步骤仅列附件 -->
          <template v-else>
            <template v-if="stepType(step) === 'UPLOAD' || stepType(step) === 'PHOTO' || stepType(step) === 'SIGNATURE'">
              <ul class="att-list">
                <li v-for="a in stepAttachments[step.id] || []" :key="a.id">
                  {{ a.file_name }}
                </li>
              </ul>
            </template>
            <template v-else>
              <span class="step-readonly-value">{{
                isMulti(step)
                  ? (Array.isArray(step.response.values) ? step.response.values.join('、') : '—')
                  : (step.response.value ?? '—')
              }}</span>
              <span v-if="step.notes" class="step-hint">备注：{{ step.notes }}</span>
            </template>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.execution-tab {
  padding: 16px 0;
}
.procedure-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 15px;
}
.procedure-code {
  color: var(--el-text-color-secondary);
}
.procedure-name {
  font-weight: 600;
}
.steps-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.step-row {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 12px 14px;
}
.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.step-code {
  font-weight: 600;
}
.step-done-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.step-body {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.step-input {
  max-width: 240px;
}
.step-notes {
  max-width: 320px;
}
.step-actions {
  display: flex;
  gap: 8px;
}
.step-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.step-readonly-value {
  font-size: 14px;
}
.att-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}
</style>
