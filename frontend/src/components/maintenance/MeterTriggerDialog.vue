<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createTrigger, updateTrigger } from '@/api/meters'
import { listUsers } from '@/api/users'
import { listTeams } from '@/api/teams'
import { listProceduresMini } from '@/api/procedures'
import type { MeterComparator, TriggerRead, WorkOrderPriority } from '@/types/maintenance'
import type { ProcedureMini } from '@/types/maintenance'
import type { UserRead, TeamRead } from '@/types/platform'

const props = defineProps<{
  visible: boolean
  meterId: string
  editing: TriggerRead | null
}>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'saved'): void
}>()

// ── constants ──────────────────────────────────────────────
const COMPARATOR_OPTIONS: { value: MeterComparator; label: string }[] = [
  { value: 'LESS_THAN', label: '小于' },
  { value: 'MORE_THAN', label: '大于' },
]
const PRIORITY_OPTIONS: { value: WorkOrderPriority; label: string }[] = [
  { value: 'NONE', label: '无' },
  { value: 'LOW', label: '低' },
  { value: 'MEDIUM', label: '中' },
  { value: 'HIGH', label: '高' },
]

// ── state ──────────────────────────────────────────────────
const users = ref<UserRead[]>([])
const teams = ref<TeamRead[]>([])
const procedures = ref<ProcedureMini[]>([])
const submitting = ref(false)

interface FormState {
  name: string
  comparator: MeterComparator
  threshold: string
  priority: WorkOrderPriority
  title: string
  description: string
  primary_user_id: string | null
  procedure_id: string | null
  assignee_ids: string[]
  team_ids: string[]
}
const form = reactive<FormState>({
  name: '',
  comparator: 'MORE_THAN',
  threshold: '',
  priority: 'NONE',
  title: '',
  description: '',
  primary_user_id: null,
  procedure_id: null,
  assignee_ids: [],
  team_ids: [],
})

async function fetchOptions() {
  try {
    const [u, t, p] = await Promise.all([listUsers(), listTeams(), listProceduresMini()])
    users.value = u
    teams.value = t
    procedures.value = p
  } catch {
    ElMessage.error('加载选项失败，请重试')
  }
}

function resetOrFill() {
  if (!props.editing) {
    form.name = ''
    form.comparator = 'MORE_THAN'
    form.threshold = ''
    form.priority = 'NONE'
    form.title = ''
    form.description = ''
    form.primary_user_id = null
    form.procedure_id = null
    form.assignee_ids = []
    form.team_ids = []
    return
  }
  form.name = props.editing.name
  form.comparator = props.editing.comparator
  form.threshold = props.editing.threshold
  form.priority = props.editing.priority
  form.title = props.editing.title
  form.description = props.editing.description
  form.primary_user_id = props.editing.primary_user_id
  form.procedure_id = props.editing.procedure_id
  form.assignee_ids = [...props.editing.assignee_ids]
  form.team_ids = [...props.editing.team_ids]
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      void fetchOptions()
      resetOrFill()
    }
  },
  { immediate: true },
)

async function submitForm() {
  if (!form.name.trim() || !form.threshold || !form.title.trim()) {
    ElMessage.warning('请填写名称、阈值与生单标题')
    return
  }
  const payload = {
    name: form.name.trim(),
    comparator: form.comparator,
    threshold: form.threshold,
    priority: form.priority,
    title: form.title.trim(),
    description: form.description,
    primary_user_id: form.primary_user_id || null,
    procedure_id: form.procedure_id || null,
    assignee_ids: form.assignee_ids,
    team_ids: form.team_ids,
  }
  submitting.value = true
  try {
    if (props.editing) {
      await updateTrigger(props.meterId, props.editing.id, payload)
    } else {
      await createTrigger(props.meterId, payload)
    }
    ElMessage.success('保存成功')
    emit('saved')
    emit('update:visible', false)
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// expose for tests (drive form / submit directly)
defineExpose({ form, submitForm })
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="触发器"
    width="640px"
    :close-on-click-modal="false"
    append-to-body
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <el-form label-width="100px" @submit.prevent="submitForm">
      <el-form-item label="名称" required>
        <el-input v-model="form.name" placeholder="请输入触发器名称" />
      </el-form-item>
      <el-form-item label="比较符">
        <el-select v-model="form.comparator" style="width: 100%">
          <el-option
            v-for="c in COMPARATOR_OPTIONS"
            :key="c.value"
            :label="c.label"
            :value="c.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="阈值" required>
        <el-input v-model="form.threshold" placeholder="阈值" />
      </el-form-item>
      <el-form-item label="优先级">
        <el-select v-model="form.priority" style="width: 100%">
          <el-option
            v-for="p in PRIORITY_OPTIONS"
            :key="p.value"
            :label="p.label"
            :value="p.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="生单标题" required>
        <el-input v-model="form.title" placeholder="触发时生成的工单标题" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
      </el-form-item>
      <el-form-item label="负责人">
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
      <el-form-item label="协办人">
        <el-select
          v-model="form.assignee_ids"
          placeholder="请选择协办人"
          multiple
          filterable
          style="width: 100%"
        >
          <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="团队">
        <el-select v-model="form.team_ids" placeholder="请选择团队" multiple style="width: 100%">
          <el-option v-for="t in teams" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关联程序">
        <el-select
          v-model="form.procedure_id"
          placeholder="请选择程序"
          clearable
          filterable
          style="width: 100%"
        >
          <el-option v-for="pr in procedures" :key="pr.id" :label="pr.name" :value="pr.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      <el-button @click="emit('update:visible', false)">取消</el-button>
    </template>
  </el-dialog>
</template>
