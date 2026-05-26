<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, updateSettings } from '@/api/settings'
import type { SettingsOut, SettingsUpdate } from '@/types/settings'

const settings = ref<SettingsOut | null>(null)
const form = ref<SettingsUpdate>({
  enable_approval_workflow: false,
  max_version_number: 100,
  require_read_confirmation: false,
  default_risk_level: 1,
  default_quality_level: 1,
})
const saving = ref(false)
const loading = ref(false)

async function loadSettings() {
  loading.value = true
  try {
    const data = await getSettings()
    settings.value = data
    form.value = {
      enable_approval_workflow: data.enable_approval_workflow,
      max_version_number: data.max_version_number,
      require_read_confirmation: data.require_read_confirmation,
      default_risk_level: data.default_risk_level,
      default_quality_level: data.default_quality_level,
    }
  } catch {
    ElMessage.error('加载设置失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!settings.value) return
  saving.value = true
  try {
    const updated = await updateSettings(form.value, settings.value.revision)
    settings.value = updated
    form.value = {
      enable_approval_workflow: updated.enable_approval_workflow,
      max_version_number: updated.max_version_number,
      require_read_confirmation: updated.require_read_confirmation,
      default_risk_level: updated.default_risk_level,
      default_quality_level: updated.default_quality_level,
    }
    ElMessage.success('保存成功')
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 412) {
      ElMessage.error('设置已被他人修改，请刷新后重试')
      await loadSettings() // refresh to get latest revision
    } else {
      ElMessage.error('保存失败，请重试')
    }
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <div class="settings-page">
    <h2 class="page-title">系统设置</h2>
    <el-card v-loading="loading">
      <el-form :model="form" label-width="180px">
        <el-form-item label="启用审批流程">
          <el-switch v-model="form.enable_approval_workflow" />
        </el-form-item>
        <el-form-item label="最大版本号">
          <el-input-number v-model="form.max_version_number" :min="1" :max="9999" />
        </el-form-item>
        <el-form-item label="需要阅读确认">
          <el-switch v-model="form.require_read_confirmation" />
        </el-form-item>
        <el-form-item label="默认风险级别">
          <el-input-number v-model="form.default_risk_level" :min="1" :max="5" />
        </el-form-item>
        <el-form-item label="默认质量级别">
          <el-input-number v-model="form.default_quality_level" :min="1" :max="5" />
        </el-form-item>
        <el-divider />
        <el-form-item label="启用版本控制">
          <span class="readonly-value">{{ settings?.enable_version_control ? '是' : '否' }}</span>
        </el-form-item>
        <el-form-item label="自动归档天数">
          <span class="readonly-value">{{ settings?.auto_archive_days ?? '-' }} 天</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" :disabled="loading" @click="handleSave">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 700px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary, #303133);
}
.readonly-value {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
</style>
