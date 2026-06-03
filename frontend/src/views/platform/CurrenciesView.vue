<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listCurrencies, createCurrency, deleteCurrency } from '@/api/currencies'
import type { Currency, CurrencyCreate } from '@/types/platform'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const isSuperAdmin = computed(() => auth.user?.role_code === 'super_admin')

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const currencies = ref<Currency[]>([])

// ── fetch ──────────────────────────────────────────────────
async function fetchCurrencies() {
  loading.value = true
  try {
    currencies.value = await listCurrencies()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchCurrencies()
})

// ── dialog ─────────────────────────────────────────────────
const dialogVisible = ref(false)
const submitting = ref(false)

interface FormState {
  code: string
  name: string
  symbol: string
}

const form = reactive<FormState>({
  code: '',
  name: '',
  symbol: '',
})

function resetForm() {
  form.code = ''
  form.name = ''
  form.symbol = ''
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.code.trim()) {
    ElMessage.warning('请填写货币代码')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('请填写货币名称')
    return
  }

  submitting.value = true
  try {
    const payload: CurrencyCreate = {
      code: form.code,
      name: form.name,
      symbol: form.symbol,
    }
    await createCurrency(payload)
    ElMessage.success('货币创建成功')
    dialogVisible.value = false
    await fetchCurrencies()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: Currency) {
  try {
    await ElMessageBox.confirm(`确认删除货币「${row.code}」？`, '删除货币', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteCurrency(row.id)
    ElMessage.success('已删除')
    await fetchCurrencies()
  } catch {
    // cancelled or error handled by interceptor
  }
}
</script>

<template>
  <div class="currencies-view">
    <h2 class="page-title">货币管理</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="isSuperAdmin" type="primary" @click="openCreate"> 新增货币 </el-button>
    </div>

    <!-- currencies table -->
    <el-table v-loading="loading" :data="currencies" border style="width: 100%; margin-top: 16px">
      <el-table-column prop="code" label="代码" min-width="140" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="symbol" label="符号" width="120" align="center" />
      <el-table-column v-if="isSuperAdmin" label="操作" width="120" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="danger" @click="handleDelete(row)"> 删除 </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- create dialog -->
    <el-dialog v-model="dialogVisible" title="新增货币" width="480px" :close-on-click-modal="false">
      <el-form label-width="80px" @submit.prevent="submitForm">
        <el-form-item label="代码" required>
          <el-input v-model="form.code" placeholder="请输入货币代码" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入货币名称" />
        </el-form-item>
        <el-form-item label="符号">
          <el-input v-model="form.symbol" placeholder="请输入货币符号" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.currencies-view {
  max-width: 1100px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary, #1a1a1a);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
