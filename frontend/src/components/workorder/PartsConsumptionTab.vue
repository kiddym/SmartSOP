<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listPartConsumptions, consumePart } from '@/api/partConsumptions'
import { listPartsMini } from '@/api/parts'
import { useAuthStore } from '@/store/auth'
import type { PartConsumptionRead, PartMini } from '@/types/inventory'

const props = defineProps<{ workOrderId: string }>()

const auth = useAuthStore()

const loading = ref(false)
const rows = ref<PartConsumptionRead[]>([])
const parts = ref<PartMini[]>([])

const addVisible = ref(false)
const submitting = ref(false)
const form = ref<{ part_id: string; quantity: string }>({ part_id: '', quantity: '1' })

const canConsume = computed(() => auth.hasPermission('part.consume'))

const totalCost = computed(() =>
  rows.value.reduce((sum, r) => sum + Number(r.total_cost), 0).toFixed(2),
)

function partLabel(id: string): string {
  const p = parts.value.find((x) => x.id === id)
  return p ? `${p.custom_id} ${p.name}` : '(已删除)'
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [c, p] = await Promise.all([listPartConsumptions(props.workOrderId), listPartsMini()])
    rows.value = c
    parts.value = p
  } catch {
    ElMessage.error('加载备件消耗失败，请重试')
  } finally {
    loading.value = false
  }
}

function openAdd(): void {
  form.value = { part_id: '', quantity: '1' }
  addVisible.value = true
}

async function submit(): Promise<void> {
  if (!form.value.part_id) {
    ElMessage.warning('请选择备件')
    return
  }
  if (!form.value.quantity || Number(form.value.quantity) <= 0) {
    ElMessage.warning('数量需大于 0')
    return
  }
  submitting.value = true
  try {
    await consumePart(props.workOrderId, {
      part_id: form.value.part_id,
      quantity: form.value.quantity,
    })
    ElMessage.success('已登记备件消耗')
    addVisible.value = false
    await load()
  } catch {
    ElMessage.error('登记失败，请检查库存或重试')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar">
      <span class="total">合计成本：¥{{ totalCost }}</span>
      <el-button v-if="canConsume" type="primary" data-test="add-consumption" @click="openAdd">
        登记消耗
      </el-button>
    </div>

    <el-table :data="rows" data-test="consumption-table">
      <el-table-column label="备件">
        <template #default="{ row }">{{ partLabel(row.part_id) }}</template>
      </el-table-column>
      <el-table-column prop="quantity" label="数量" width="120" />
      <el-table-column label="单价" width="120">
        <template #default="{ row }">¥{{ Number(row.unit_cost).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="小计" width="140">
        <template #default="{ row }">¥{{ Number(row.total_cost).toFixed(2) }}</template>
      </el-table-column>
      <el-table-column label="时间" width="200">
        <template #default="{ row }">{{ new Date(row.consumed_at).toLocaleString() }}</template>
      </el-table-column>
      <template #empty>暂无备件消耗</template>
    </el-table>

    <el-dialog v-model="addVisible" title="登记备件消耗" width="480px">
      <el-form label-width="80px">
        <el-form-item label="备件">
          <el-select
            v-model="form.part_id"
            filterable
            placeholder="选择备件"
            data-test="part-select"
            style="width: 100%"
          >
            <el-option
              v-for="p in parts"
              :key="p.id"
              :label="`${p.custom_id} ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="数量">
          <el-input v-model="form.quantity" data-test="quantity" type="number" min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" data-test="submit" @click="submit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.total {
  font-weight: 600;
}
</style>
