<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listRequests,
  createRequest,
  updateRequest,
  deleteRequest,
  approveRequest,
  rejectRequest,
  cancelRequest,
  listRequestActivities,
  addRequestComment,
} from '@/api/requests'
import type { ListRequestsParams } from '@/api/requests'
import { listAssetsMini } from '@/api/assets'
import { listLocationsMini } from '@/api/locations'
import { listUsers } from '@/api/users'
import { listTeams } from '@/api/teams'
import { listProceduresMini } from '@/api/procedures'
import { getFieldConfig } from '@/api/fieldConfigurations'
import type {
  RequestRead,
  RequestStatus,
  WorkOrderPriority,
  ActivityRead,
  ProcedureMini,
} from '@/types/maintenance'
import type { AssetMini, LocationMini, AssetStatus } from '@/types/maindata'
import type { UserRead, TeamRead } from '@/types/platform'
import { useAuthStore } from '@/store/auth'
import { formatDateTime } from '@/utils/format'
import EntityAttachments from '@/components/EntityAttachments.vue'
import CustomFieldsSection from '@/components/CustomFieldsSection.vue'

const auth = useAuthStore()

// ── mappings ───────────────────────────────────────────────
const PRIORITY_LABELS: Record<WorkOrderPriority, string> = {
  NONE: '无',
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
}
const STATUS_LABELS: Record<RequestStatus, string> = {
  PENDING: '待审批',
  APPROVED: '已批准',
  REJECTED: '已驳回',
  CANCELED: '已取消',
}
const STATUS_TAG: Record<RequestStatus, string> = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
  CANCELED: 'info',
}
const STATUS_OPTIONS = (Object.keys(STATUS_LABELS) as RequestStatus[]).map((v) => ({
  value: v,
  label: STATUS_LABELS[v],
}))
// 资产状态（审批联动用）。中文同资产模块一致。
const ASSET_STATUS_LABELS: Record<AssetStatus, string> = {
  OPERATIONAL: '运行中',
  STANDBY: '待机',
  MODERNIZATION: '改造中',
  INSPECTION_SCHEDULED: '待巡检',
  COMMISSIONING: '调试中',
  EMERGENCY_SHUTDOWN: '紧急停机',
  DOWN: '停机',
}
const ASSET_STATUS_OPTIONS = (Object.keys(ASSET_STATUS_LABELS) as AssetStatus[]).map((v) => ({
  value: v,
  label: ASSET_STATUS_LABELS[v],
}))
const PRIORITY_OPTIONS = (Object.keys(PRIORITY_LABELS) as WorkOrderPriority[]).map((v) => ({
  value: v,
  label: PRIORITY_LABELS[v],
}))
function priorityLabel(p: WorkOrderPriority): string {
  return PRIORITY_LABELS[p]
}
function statusLabel(s: RequestStatus): string {
  return STATUS_LABELS[s]
}
function statusTag(s: RequestStatus): string {
  return STATUS_TAG[s]
}

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const requests = ref<RequestRead[]>([])
const assetsMini = ref<AssetMini[]>([])
const locationsMini = ref<LocationMini[]>([])
const users = ref<UserRead[]>([])
const teams = ref<TeamRead[]>([])
const procedures = ref<ProcedureMini[]>([])

// ── 请求表单字段配置（FieldConfiguration，form_key=REQUEST）──
// 默认：全部字段可见、按原有规则（仅 title 必填）。加载失败时降级保持此默认，不阻断建单。
const REQUEST_FIELDS = ['description', 'priority', 'due_date', 'asset', 'location'] as const
type RequestField = (typeof REQUEST_FIELDS)[number]
const fieldVisible = reactive<Record<RequestField, boolean>>({
  description: true,
  priority: true,
  due_date: true,
  asset: true,
  location: true,
})
const fieldRequired = reactive<Record<RequestField, boolean>>({
  description: false,
  priority: false,
  due_date: false,
  asset: false,
  location: false,
})

async function fetchFieldConfig() {
  try {
    const cfg = await getFieldConfig('REQUEST')
    for (const item of cfg) {
      if ((REQUEST_FIELDS as readonly string[]).includes(item.field_name)) {
        const key = item.field_name as RequestField
        fieldVisible[key] = item.visible
        fieldRequired[key] = item.required
      }
    }
  } catch {
    // 降级：保持全部可见、仅 title 必填的默认配置；不打断页面加载与建单。
  }
}

const filterStatus = ref<RequestStatus | ''>('')
const filterPriority = ref<WorkOrderPriority | ''>('')
const filterAsset = ref('')
const filterLocation = ref('')

// ── mapping helpers ────────────────────────────────────────
function assetName(id: string | null): string {
  if (!id) return '—'
  const a = assetsMini.value.find((x) => x.id === id)
  return a ? a.name : '—'
}
function locationName(id: string | null): string {
  if (!id) return '—'
  const l = locationsMini.value.find((x) => x.id === id)
  return l ? l.name : '—'
}
function userName(id: string | null): string {
  if (!id) return '—'
  const u = users.value.find((x) => x.id === id)
  return u ? u.name : '—'
}

// ── fetch ──────────────────────────────────────────────────
async function fetchRequests() {
  loading.value = true
  try {
    const params: ListRequestsParams = {}
    if (filterStatus.value) params.status = filterStatus.value
    if (filterPriority.value) params.priority = filterPriority.value
    if (filterAsset.value) params.asset_id = filterAsset.value
    if (filterLocation.value) params.location_id = filterLocation.value
    requests.value = await listRequests(params)
  } finally {
    loading.value = false
  }
}
async function fetchAssetsMini() {
  assetsMini.value = await listAssetsMini()
}
async function fetchLocationsMini() {
  locationsMini.value = await listLocationsMini()
}
async function fetchUsers() {
  users.value = await listUsers()
}
async function fetchTeams() {
  teams.value = await listTeams()
}
async function fetchProcedures() {
  procedures.value = await listProceduresMini()
}

onMounted(async () => {
  await Promise.all([
    fetchRequests(),
    fetchAssetsMini(),
    fetchLocationsMini(),
    fetchUsers(),
    fetchTeams(),
    fetchProcedures(),
    fetchFieldConfig(),
  ])
})

// ── create / edit dialog ───────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const editingId = ref('')
const submitting = ref(false)

interface FormState {
  title: string
  description: string
  priority: WorkOrderPriority
  due_date: string | null
  asset_id: string | null
  location_id: string | null
  custom_values: Record<string, unknown>
}
const form = reactive<FormState>({
  title: '',
  description: '',
  priority: 'NONE',
  due_date: null,
  asset_id: null,
  location_id: null,
  custom_values: {},
})

function resetForm() {
  form.title = ''
  form.description = ''
  form.priority = 'NONE'
  form.due_date = null
  form.asset_id = null
  form.location_id = null
  form.custom_values = {}
}

function openCreate() {
  resetForm()
  dialogMode.value = 'create'
  editingId.value = ''
  dialogVisible.value = true
}

function openEdit(row: RequestRead) {
  resetForm()
  Object.assign(form, {
    title: row.title,
    description: row.description,
    priority: row.priority,
    due_date: row.due_date,
    asset_id: row.asset_id,
    location_id: row.location_id,
    custom_values: { ...(row.custom_values ?? {}) },
  })
  dialogMode.value = 'edit'
  editingId.value = row.id
  dialogVisible.value = true
}

// 按配置校验可见且必填的字段（title 不受配置影响，始终必填）。
function validateRequiredFields(): string | null {
  if (!form.title.trim()) return '标题'
  if (fieldVisible.description && fieldRequired.description && !form.description.trim())
    return '描述'
  if (fieldVisible.priority && fieldRequired.priority && (!form.priority || form.priority === 'NONE'))
    return '优先级'
  if (fieldVisible.due_date && fieldRequired.due_date && !form.due_date) return '截止日期'
  if (fieldVisible.asset && fieldRequired.asset && !form.asset_id) return '资产'
  if (fieldVisible.location && fieldRequired.location && !form.location_id) return '位置'
  return null
}

async function submitForm() {
  const missing = validateRequiredFields()
  if (missing) {
    ElMessage.warning(`请填写${missing}`)
    return
  }
  const payload = {
    title: form.title.trim(),
    description: form.description,
    priority: form.priority,
    due_date: form.due_date || null,
    asset_id: form.asset_id || null,
    location_id: form.location_id || null,
    custom_values: form.custom_values,
  }
  try {
    submitting.value = true
    if (dialogMode.value === 'create') {
      await createRequest(payload)
    } else {
      await updateRequest(editingId.value, payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await fetchRequests()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── approve dialog ─────────────────────────────────────────
const approveVisible = ref(false)
const approvingId = ref('')
const approveSubmitting = ref(false)

interface ApproveFormState {
  primary_user_id: string | null
  assignee_ids: string[]
  team_ids: string[]
  procedure_id: string | null
  note: string
  asset_status: AssetStatus | null
}
const approveForm = reactive<ApproveFormState>({
  primary_user_id: null,
  assignee_ids: [],
  team_ids: [],
  procedure_id: null,
  note: '',
  asset_status: null,
})
// 当前审批请求关联的资产 id（决定是否显示资产状态选择）。
const approvingAssetId = ref<string | null>(null)

function openApprove(row: RequestRead) {
  approveForm.primary_user_id = null
  approveForm.assignee_ids = []
  approveForm.team_ids = []
  approveForm.procedure_id = null
  approveForm.note = ''
  approveForm.asset_status = null
  approvingId.value = row.id
  approvingAssetId.value = row.asset_id
  approveVisible.value = true
}

async function submitApprove() {
  const payload = {
    note: approveForm.note,
    primary_user_id: approveForm.primary_user_id || null,
    assignee_ids: approveForm.assignee_ids,
    team_ids: approveForm.team_ids,
    procedure_id: approveForm.procedure_id || null,
    // 仅当请求关联了资产且选择了状态时附带，避免空值误传。
    asset_status:
      approvingAssetId.value && approveForm.asset_status ? approveForm.asset_status : null,
  }
  try {
    approveSubmitting.value = true
    await approveRequest(approvingId.value, payload)
    ElMessage.success('审批通过，已生成工单')
    approveVisible.value = false
    await fetchRequests()
  } catch {
    ElMessage.error('操作失败，请重试')
  } finally {
    approveSubmitting.value = false
  }
}

// ── reject / cancel ────────────────────────────────────────
async function handleReject(row: RequestRead) {
  const res = await ElMessageBox.prompt('请输入驳回原因', '驳回请求', {
    inputType: 'textarea',
  }).catch(() => null)
  if (!res) return
  try {
    await rejectRequest(row.id, { reason: res.value || '' })
    ElMessage.success('已驳回')
    await fetchRequests()
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

async function handleCancel(row: RequestRead) {
  const res = await ElMessageBox.prompt('请输入取消原因', '取消请求', {
    inputType: 'textarea',
  }).catch(() => null)
  if (!res) return
  try {
    await cancelRequest(row.id, { reason: res.value || '' })
    ElMessage.success('已取消')
    await fetchRequests()
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

// ── activity timeline ──────────────────────────────────────
const activityVisible = ref(false)
const activities = ref<ActivityRead[]>([])
const activeReqId = ref('')
const commentText = ref('')

async function openActivities(row: RequestRead) {
  activeReqId.value = row.id
  activities.value = await listRequestActivities(row.id)
  commentText.value = ''
  activityVisible.value = true
}

async function submitComment() {
  if (!commentText.value.trim()) return
  try {
    await addRequestComment(activeReqId.value, { comment: commentText.value.trim() })
    commentText.value = ''
    activities.value = await listRequestActivities(activeReqId.value)
  } catch {
    ElMessage.error('操作失败，请重试')
  }
}

// ── attachments ────────────────────────────────────────────
const attachmentsVisible = ref(false)
const attachmentReqId = ref('')

function openAttachments(row: RequestRead) {
  attachmentReqId.value = row.id
  attachmentsVisible.value = true
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: RequestRead) {
  try {
    await ElMessageBox.confirm(`确认删除请求「${row.custom_id}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteRequest(row.id)
    ElMessage.success('已删除')
    await fetchRequests()
  } catch {
    // cancelled or error handled by interceptor
  }
}

// expose for tests (drive dialogs / forms directly)
defineExpose({
  openApprove,
  approveForm,
  openEdit,
  openCreate,
  handleReject,
  handleCancel,
  openActivities,
  openAttachments,
  approvingAssetId,
  fieldVisible,
  fieldRequired,
})
</script>

<template>
  <div class="page">
    <h2 class="page-title">维护请求</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('request.create')" type="primary" @click="openCreate">
        新建请求
      </el-button>
      <el-select
        v-model="filterStatus"
        placeholder="按状态筛选"
        clearable
        style="width: 160px"
        @change="fetchRequests"
      >
        <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-select
        v-model="filterPriority"
        placeholder="按优先级筛选"
        clearable
        style="width: 160px"
        @change="fetchRequests"
      >
        <el-option v-for="p in PRIORITY_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
      </el-select>
      <el-select
        v-model="filterAsset"
        placeholder="按资产筛选"
        clearable
        filterable
        style="width: 200px"
        @change="fetchRequests"
      >
        <el-option v-for="a in assetsMini" :key="a.id" :label="a.name" :value="a.id" />
      </el-select>
      <el-select
        v-model="filterLocation"
        placeholder="按位置筛选"
        clearable
        filterable
        style="width: 200px"
        @change="fetchRequests"
      >
        <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
      </el-select>
    </div>

    <!-- requests table -->
    <el-table
      v-loading="loading"
      :data="requests"
      row-key="id"
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column prop="custom_id" label="编号" min-width="110" />
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column label="优先级" min-width="90" align="center">
        <template #default="{ row }">{{ priorityLabel(row.priority) }}</template>
      </el-table-column>
      <el-table-column label="状态" min-width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="资产" min-width="140">
        <template #default="{ row }">{{ assetName(row.asset_id) }}</template>
      </el-table-column>
      <el-table-column label="位置" min-width="140">
        <template #default="{ row }">{{ locationName(row.location_id) }}</template>
      </el-table-column>
      <el-table-column label="到期" min-width="120">
        <template #default="{ row }">{{ row.due_date || '—' }}</template>
      </el-table-column>
      <el-table-column label="工单" min-width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.work_order_id" type="info">已生成工单</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'PENDING' && auth.hasPermission('request.create')"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="row.status === 'PENDING' && auth.hasPermission('request.approve')"
            link
            type="success"
            @click="openApprove(row)"
          >
            审批
          </el-button>
          <el-button
            v-if="row.status === 'PENDING' && auth.hasPermission('request.approve')"
            link
            type="warning"
            @click="handleReject(row)"
          >
            驳回
          </el-button>
          <el-button
            v-if="row.status === 'PENDING' && auth.hasPermission('request.cancel')"
            link
            @click="handleCancel(row)"
          >
            取消
          </el-button>
          <el-button link type="primary" @click="openActivities(row)">活动</el-button>
          <el-button link type="primary" @click="openAttachments(row)">附件</el-button>
          <el-button
            v-if="auth.hasPermission('request.delete')"
            link
            type="danger"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新建请求' : '编辑请求'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px" @submit.prevent="submitForm">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="请输入标题" />
        </el-form-item>
        <el-form-item v-if="fieldVisible.description" label="描述" :required="fieldRequired.description">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item v-if="fieldVisible.priority" label="优先级" :required="fieldRequired.priority">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option
              v-for="p in PRIORITY_OPTIONS"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="fieldVisible.due_date" label="到期日" :required="fieldRequired.due_date">
          <el-date-picker
            v-model="form.due_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择到期日"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-if="fieldVisible.asset" label="资产" :required="fieldRequired.asset">
          <el-select
            v-model="form.asset_id"
            placeholder="请选择资产"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="a in assetsMini" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="fieldVisible.location" label="位置" :required="fieldRequired.location">
          <el-select
            v-model="form.location_id"
            placeholder="请选择位置"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <CustomFieldsSection entity-type="request" v-model="form.custom_values" />
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
        <el-button @click="dialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- approve dialog -->
    <el-dialog
      v-model="approveVisible"
      title="审批请求"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px">
        <el-form-item label="负责人">
          <el-select
            v-model="approveForm.primary_user_id"
            placeholder="请选择负责人"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="协办人">
          <el-select
            v-model="approveForm.assignee_ids"
            placeholder="请选择协办人"
            multiple
            filterable
            style="width: 100%"
          >
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="团队">
          <el-select
            v-model="approveForm.team_ids"
            placeholder="请选择团队"
            multiple
            style="width: 100%"
          >
            <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联程序">
          <el-select
            v-model="approveForm.procedure_id"
            placeholder="请选择程序"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="pr in procedures" :key="pr.id" :label="pr.name" :value="pr.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="approvingAssetId" label="资产状态">
          <el-select
            v-model="approveForm.asset_status"
            placeholder="可选：审批后同步资产状态"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="s in ASSET_STATUS_OPTIONS"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="approveForm.note" type="textarea" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="approveSubmitting" @click="submitApprove">
          批准并生成工单
        </el-button>
        <el-button @click="approveVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- activity dialog -->
    <el-dialog v-model="activityVisible" title="活动时间线" width="600px">
      <el-timeline>
        <el-timeline-item
          v-for="a in activities"
          :key="a.id"
          :timestamp="formatDateTime(a.created_at)"
        >
          <span v-if="a.actor_user_id">{{ userName(a.actor_user_id) }}：</span>
          {{ a.comment || a.activity_type }}
        </el-timeline-item>
      </el-timeline>
      <div class="comment-box">
        <el-input v-model="commentText" type="textarea" placeholder="请输入评论" :rows="2" />
        <el-button
          v-if="auth.hasPermission('request.view')"
          type="primary"
          style="margin-top: 8px"
          @click="submitComment"
        >
          发表评论
        </el-button>
      </div>
    </el-dialog>

    <!-- attachments dialog -->
    <el-dialog v-model="attachmentsVisible" title="请求附件" width="700px">
      <EntityAttachments
        v-if="attachmentsVisible"
        entity-type="request"
        :entity-id="attachmentReqId"
        :editable="auth.hasPermission('request.create')"
      />
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  max-width: 1200px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.comment-box {
  margin-top: 12px;
}
</style>
