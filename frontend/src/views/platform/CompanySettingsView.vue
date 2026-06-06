<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getCompanySettings, updateCompanySettings } from '@/api/companySettings'
import { listCurrencies } from '@/api/currencies'
import type { CompanySettings, Currency } from '@/types/platform'
import { useAuthStore } from '@/store/auth'
import { useCompanySettingsStore } from '@/store/companySettings'

const auth = useAuthStore()
const companySettingsStore = useCompanySettingsStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const saving = ref(false)
const currencies = ref<Currency[]>([])

const form = reactive<CompanySettings>({
  date_format: '',
  timezone: '',
  default_currency_code: '',
  auto_assign: false,
  show_requests: true,
  show_locations: true,
  show_meters: true,
  show_vendors_customers: true,
})

const canEdit = computed(() => auth.hasPermission('company.settings'))

const DATE_FORMATS = ['YYYY-MM-DD', 'YYYY/MM/DD', 'DD/MM/YYYY', 'MM/DD/YYYY']

// ── fetch ──────────────────────────────────────────────────
async function fetchSettings() {
  loading.value = true
  try {
    Object.assign(form, await getCompanySettings())
  } finally {
    loading.value = false
  }
}

async function fetchCurrencies() {
  currencies.value = await listCurrencies()
}

onMounted(async () => {
  await Promise.all([fetchSettings(), fetchCurrencies()])
})

// ── save ───────────────────────────────────────────────────
async function handleSave() {
  try {
    saving.value = true
    const updated = await updateCompanySettings({ ...form })
    Object.assign(form, updated)
    // 同步轻量缓存，使侧栏导航显隐即时生效。
    companySettingsStore.settings = updated
    ElMessage.success('保存成功')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="company-settings-view">
    <h2 class="page-title">公司设置</h2>

    <el-form v-loading="loading" label-width="120px" class="settings-form">
      <el-form-item label="日期格式">
        <el-select
          v-model="form.date_format"
          :disabled="!canEdit"
          placeholder="请选择日期格式"
          style="width: 100%"
        >
          <el-option v-for="f in DATE_FORMATS" :key="f" :label="f" :value="f" />
        </el-select>
      </el-form-item>

      <el-form-item label="时区">
        <el-input v-model="form.timezone" :disabled="!canEdit" placeholder="如 Asia/Shanghai" />
      </el-form-item>

      <el-form-item label="默认币种">
        <el-select
          v-model="form.default_currency_code"
          :disabled="!canEdit"
          placeholder="请选择默认币种"
          style="width: 100%"
        >
          <el-option
            v-for="c in currencies"
            :key="c.id"
            :label="`${c.code}（${c.name}）`"
            :value="c.code"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="自动派单">
        <el-switch v-model="form.auto_assign" :disabled="!canEdit" />
      </el-form-item>

      <el-divider content-position="left">导航模块显隐</el-divider>

      <el-form-item label="显示请求模块">
        <el-switch v-model="form.show_requests" :disabled="!canEdit" />
      </el-form-item>

      <el-form-item label="显示位置模块">
        <el-switch v-model="form.show_locations" :disabled="!canEdit" />
      </el-form-item>

      <el-form-item label="显示计量模块">
        <el-switch v-model="form.show_meters" :disabled="!canEdit" />
      </el-form-item>

      <el-form-item label="显示供应商与客户模块">
        <el-switch v-model="form.show_vendors_customers" :disabled="!canEdit" />
      </el-form-item>

      <el-form-item v-if="canEdit">
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.company-settings-view {
  max-width: 720px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary, #1a1a1a);
}
.settings-form {
  margin-top: 8px;
}
</style>
