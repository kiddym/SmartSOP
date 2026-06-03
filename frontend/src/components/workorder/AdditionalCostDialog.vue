<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createAdditionalCost, updateAdditionalCost } from '@/api/workOrders'
import { listCostCategories } from '@/api/costCategories'
import type { AdditionalCostRead, CostCategoryRead } from '@/types/workOrder'

const props = defineProps<{
  visible: boolean
  workOrderId: string
  editing: AdditionalCostRead | null
}>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'saved'): void
}>()

// ── state ──────────────────────────────────────────────────
const costCategories = ref<CostCategoryRead[]>([])
const submitting = ref(false)

interface FormState {
  title: string
  amount: string
  cost_category_id: string | null
  description: string
}
const form = reactive<FormState>({
  title: '',
  amount: '',
  cost_category_id: null,
  description: '',
})

async function fetchOptions() {
  try {
    costCategories.value = await listCostCategories()
  } catch {
    ElMessage.error('加载选项失败，请重试')
  }
}

function resetOrFill() {
  if (!props.editing) {
    form.title = ''
    form.amount = ''
    form.cost_category_id = null
    form.description = ''
    return
  }
  form.title = props.editing.title
  form.amount = props.editing.amount
  form.cost_category_id = props.editing.cost_category_id
  form.description = props.editing.description
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
  if (!form.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  if (!form.amount) {
    ElMessage.warning('请填写金额')
    return
  }
  const payload = {
    title: form.title.trim(),
    amount: form.amount,
    cost_category_id: form.cost_category_id || null,
    description: form.description,
  }
  submitting.value = true
  try {
    if (props.editing) {
      await updateAdditionalCost(props.workOrderId, props.editing.id, payload)
    } else {
      await createAdditionalCost(props.workOrderId, payload)
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
    :title="editing ? '编辑额外成本' : '新增额外成本'"
    width="520px"
    :close-on-click-modal="false"
    append-to-body
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <el-form label-width="100px" @submit.prevent="submitForm">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" placeholder="请输入标题" />
      </el-form-item>
      <el-form-item label="金额" required>
        <el-input v-model="form.amount" placeholder="请输入金额" />
      </el-form-item>
      <el-form-item label="成本类别">
        <el-select
          v-model="form.cost_category_id"
          placeholder="请选择成本类别"
          clearable
          style="width: 100%"
        >
          <el-option v-for="cc in costCategories" :key="cc.id" :label="cc.name" :value="cc.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      <el-button @click="emit('update:visible', false)">取消</el-button>
    </template>
  </el-dialog>
</template>
