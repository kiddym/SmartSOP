<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createLabor, updateLabor } from '@/api/workOrders'
import { listUsers } from '@/api/users'
import { listTimeCategories } from '@/api/timeCategories'
import type { LaborRead, TimeCategoryRead } from '@/types/workOrder'
import type { UserRead } from '@/types/platform'

const props = defineProps<{
  visible: boolean
  workOrderId: string
  editing: LaborRead | null
}>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'saved'): void
}>()

// ── state ──────────────────────────────────────────────────
const users = ref<UserRead[]>([])
const timeCategories = ref<TimeCategoryRead[]>([])
const submitting = ref(false)

interface FormState {
  minutes: number
  user_id: string | null
  time_category_id: string | null
  hourly_rate: string
  notes: string
}
const form = reactive<FormState>({
  minutes: 0,
  user_id: null,
  time_category_id: null,
  hourly_rate: '',
  notes: '',
})

async function fetchOptions() {
  try {
    const [u, tc] = await Promise.all([listUsers(), listTimeCategories()])
    users.value = u
    timeCategories.value = tc
  } catch {
    ElMessage.error('加载选项失败，请重试')
  }
}

function resetOrFill() {
  if (!props.editing) {
    form.minutes = 0
    form.user_id = null
    form.time_category_id = null
    form.hourly_rate = ''
    form.notes = ''
    return
  }
  form.minutes = Math.round(props.editing.duration_seconds / 60)
  form.user_id = props.editing.user_id
  form.time_category_id = props.editing.time_category_id
  form.hourly_rate = props.editing.hourly_rate
  form.notes = props.editing.notes
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
  const duration_seconds = Math.round(form.minutes) * 60
  const payload = {
    duration_seconds,
    user_id: form.user_id || null,
    time_category_id: form.time_category_id || null,
    hourly_rate: form.hourly_rate || null,
    notes: form.notes,
  }
  submitting.value = true
  try {
    if (props.editing) {
      await updateLabor(props.workOrderId, props.editing.id, payload)
    } else {
      await createLabor(props.workOrderId, payload)
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

defineExpose({ form, submitForm })
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="editing ? '编辑工时' : '新增工时'"
    width="560px"
    :close-on-click-modal="false"
    append-to-body
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <el-form label-width="100px" @submit.prevent="submitForm">
      <el-form-item label="执行人">
        <el-select
          v-model="form.user_id"
          placeholder="请选择执行人"
          clearable
          filterable
          style="width: 100%"
        >
          <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="工时类别">
        <el-select
          v-model="form.time_category_id"
          placeholder="请选择工时类别"
          clearable
          style="width: 100%"
        >
          <el-option v-for="tc in timeCategories" :key="tc.id" :label="tc.name" :value="tc.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="时长（分钟）">
        <el-input-number v-model="form.minutes" :min="0" style="width: 100%" />
      </el-form-item>
      <el-form-item label="费率">
        <el-input v-model="form.hourly_rate" placeholder="留空则按类别" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" placeholder="请输入备注" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      <el-button @click="emit('update:visible', false)">取消</el-button>
    </template>
  </el-dialog>
</template>
