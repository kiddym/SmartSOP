<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { createWorkOrder, updateWorkOrder } from '@/api/workOrders'
import { listAssetsMini } from '@/api/assets'
import { listLocationsMini } from '@/api/locations'
import { listUsers } from '@/api/users'
import { listTeams } from '@/api/teams'
import { listProceduresMini } from '@/api/procedures'
import { listWorkOrderCategories } from '@/api/workOrderCategories'
import { getFieldConfig } from '@/api/fieldConfigurations'
import type { WorkOrderRead, WorkOrderPriority, WorkOrderCategoryRead } from '@/types/workOrder'
import type { AssetMini, LocationMini } from '@/types/maindata'
import type { UserRead, TeamRead } from '@/types/platform'
import type { ProcedureMini } from '@/types/maintenance'
import CustomFieldsSection from '@/components/CustomFieldsSection.vue'

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  editing: WorkOrderRead | null
}>()

const emit = defineEmits<{
  'update:visible': [boolean]
  saved: [WorkOrderRead | string]
}>()

// ── constants ──────────────────────────────────────────────
const PRIORITY_OPTIONS: { value: WorkOrderPriority; label: string }[] = [
  { value: 'NONE', label: '无' },
  { value: 'LOW', label: '低' },
  { value: 'MEDIUM', label: '中' },
  { value: 'HIGH', label: '高' },
]

// ── state ──────────────────────────────────────────────────
const assetsMini = ref<AssetMini[]>([])
const locationsMini = ref<LocationMini[]>([])
const users = ref<UserRead[]>([])
const teams = ref<TeamRead[]>([])
const procedures = ref<ProcedureMini[]>([])
const categories = ref<WorkOrderCategoryRead[]>([])
const submitting = ref(false)

// ── 工单表单字段配置（FieldConfiguration，form_key=WORK_ORDER）──
// 默认：全部可配置字段可见、仅 title 必填。加载失败时降级保持此默认，不阻断建单。
// 仅以下字段在本表单有对应 UI；estimated_duration / estimated_start_date 当前表单无对应控件，
// 故配置仅在配置页生效，此处不参与渲染门控。
const WO_FIELDS = [
  'description',
  'priority',
  'due_date',
  'asset',
  'location',
  'assignee',
  'team',
  'category',
] as const
type WoField = (typeof WO_FIELDS)[number]
const fieldVisible = reactive<Record<WoField, boolean>>({
  description: true,
  priority: true,
  due_date: true,
  asset: true,
  location: true,
  assignee: true,
  team: true,
  category: true,
})
const fieldRequired = reactive<Record<WoField, boolean>>({
  description: false,
  priority: false,
  due_date: false,
  asset: false,
  location: false,
  assignee: false,
  team: false,
  category: false,
})

async function fetchFieldConfig() {
  try {
    const cfg = await getFieldConfig('WORK_ORDER')
    for (const item of cfg) {
      if ((WO_FIELDS as readonly string[]).includes(item.field_name)) {
        const key = item.field_name as WoField
        fieldVisible[key] = item.visible
        fieldRequired[key] = item.required
      }
    }
  } catch {
    // 降级：保持全部可见、仅 title 必填的默认配置；不打断建单。
  }
}

onMounted(fetchFieldConfig)

interface FormState {
  title: string
  description: string
  priority: WorkOrderPriority
  due_date: string | null
  asset_id: string | null
  location_id: string | null
  primary_user_id: string | null
  assignee_ids: string[]
  team_ids: string[]
  category_id: string | null
  procedure_id: string | null
  required_signature: boolean
  custom_values: Record<string, unknown>
}

const form = reactive<FormState>({
  title: '',
  description: '',
  priority: 'NONE',
  due_date: null,
  asset_id: null,
  location_id: null,
  primary_user_id: null,
  assignee_ids: [],
  team_ids: [],
  category_id: null,
  procedure_id: null,
  required_signature: false,
  custom_values: {},
})

// ── helpers ────────────────────────────────────────────────
async function fetchOptions() {
  await Promise.all([
    listAssetsMini().then((v) => (assetsMini.value = v)),
    listLocationsMini().then((v) => (locationsMini.value = v)),
    listUsers().then((v) => (users.value = v)),
    listTeams().then((v) => (teams.value = v)),
    listProceduresMini().then((v) => (procedures.value = v)),
    listWorkOrderCategories().then((v) => (categories.value = v)),
  ])
}

function resetOrFill() {
  if (props.mode === 'create' || !props.editing) {
    form.title = ''
    form.description = ''
    form.priority = 'NONE'
    form.due_date = null
    form.asset_id = null
    form.location_id = null
    form.primary_user_id = null
    form.assignee_ids = []
    form.team_ids = []
    form.category_id = null
    form.procedure_id = null
    form.required_signature = false
    form.custom_values = {}
  } else {
    const e = props.editing
    form.title = e.title
    form.description = e.description
    form.priority = e.priority
    form.due_date = e.due_date
    form.asset_id = e.asset_id
    form.location_id = e.location_id
    form.primary_user_id = e.primary_user_id
    form.category_id = e.category_id
    form.assignee_ids = []
    form.team_ids = []
    form.procedure_id = null
    form.required_signature = e.required_signature
    form.custom_values = { ...(e.custom_values ?? {}) }
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      fetchOptions()
      resetOrFill()
    }
  },
  { immediate: true },
)

// 按配置校验可见且必填的字段（title 不受配置影响，始终必填）。
// team 字段对应「指派团队」仅 create 模式渲染，故其必填仅在 create 模式生效。
function validateRequiredFields(): string | null {
  if (!form.title.trim()) return '标题'
  if (fieldVisible.description && fieldRequired.description && !form.description.trim())
    return '描述'
  if (
    fieldVisible.priority &&
    fieldRequired.priority &&
    (!form.priority || form.priority === 'NONE')
  )
    return '优先级'
  if (fieldVisible.due_date && fieldRequired.due_date && !form.due_date) return '截止日期'
  if (fieldVisible.asset && fieldRequired.asset && !form.asset_id) return '资产'
  if (fieldVisible.location && fieldRequired.location && !form.location_id) return '位置'
  if (fieldVisible.assignee && fieldRequired.assignee && !form.primary_user_id) return '负责人'
  if (fieldVisible.category && fieldRequired.category && !form.category_id) return '分类'
  if (
    props.mode === 'create' &&
    fieldVisible.team &&
    fieldRequired.team &&
    form.team_ids.length === 0
  )
    return '团队'
  return null
}

// ── submit ─────────────────────────────────────────────────
async function submitForm() {
  const missing = validateRequiredFields()
  if (missing) {
    ElMessage.warning(`请填写${missing}`)
    return
  }
  try {
    submitting.value = true
    let result: WorkOrderRead
    if (props.mode === 'create') {
      const payload = {
        title: form.title.trim(),
        description: form.description,
        priority: form.priority,
        due_date: form.due_date || null,
        asset_id: form.asset_id || null,
        location_id: form.location_id || null,
        primary_user_id: form.primary_user_id || null,
        category_id: form.category_id || null,
        assignee_ids: form.assignee_ids,
        team_ids: form.team_ids,
        procedure_id: form.procedure_id || null,
        required_signature: form.required_signature,
        custom_values: form.custom_values,
      }
      result = await createWorkOrder(payload)
    } else {
      const payload = {
        title: form.title.trim(),
        description: form.description,
        priority: form.priority,
        due_date: form.due_date || null,
        asset_id: form.asset_id || null,
        location_id: form.location_id || null,
        primary_user_id: form.primary_user_id || null,
        category_id: form.category_id || null,
        required_signature: form.required_signature,
        custom_values: form.custom_values,
      }
      result = await updateWorkOrder(props.editing!.id, payload)
    }
    ElMessage.success('保存成功')
    emit('saved', result)
    emit('update:visible', false)
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

defineExpose({ form, submitForm, fieldVisible, fieldRequired })
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="mode === 'create' ? '新建工单' : '编辑工单'"
    width="640px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <el-form label-width="90px" @submit.prevent="submitForm">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" placeholder="请输入标题" />
      </el-form-item>
      <el-form-item
        v-if="fieldVisible.description"
        label="描述"
        :required="fieldRequired.description"
      >
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
      <el-form-item v-if="fieldVisible.category" label="分类" :required="fieldRequired.category">
        <el-select
          v-model="form.category_id"
          placeholder="请选择分类"
          clearable
          style="width: 100%"
        >
          <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="fieldVisible.assignee" label="负责人" :required="fieldRequired.assignee">
        <el-select
          v-model="form.primary_user_id"
          placeholder="请选择负责人"
          clearable
          filterable
          style="width: 100%"
        >
          <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="完成需签名">
        <el-switch v-model="form.required_signature" />
      </el-form-item>
      <!-- 仅 create 模式额外字段 -->
      <template v-if="mode === 'create'">
        <el-form-item label="指派用户">
          <el-select
            v-model="form.assignee_ids"
            placeholder="请选择指派用户"
            multiple
            filterable
            style="width: 100%"
          >
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="fieldVisible.team" label="指派团队" :required="fieldRequired.team">
          <el-select
            v-model="form.team_ids"
            placeholder="请选择指派团队"
            multiple
            style="width: 100%"
          >
            <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联 SOP">
          <el-select
            v-model="form.procedure_id"
            placeholder="请选择 SOP"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="pr in procedures" :key="pr.id" :label="pr.name" :value="pr.id" />
          </el-select>
        </el-form-item>
      </template>
      <CustomFieldsSection entity-type="work_order" v-model="form.custom_values" />
    </el-form>
    <template #footer>
      <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      <el-button @click="emit('update:visible', false)">取消</el-button>
    </template>
  </el-dialog>
</template>
