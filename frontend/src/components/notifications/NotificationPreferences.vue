<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useNotificationStore } from '@/store/notifications'
import { NOTIFICATION_TYPES } from '@/utils/notificationText'

const store = useNotificationStore()
const emailEnabled = ref(true)
const disabled = ref<Set<string>>(new Set())
const saving = ref(false)

function isOn(code: string): boolean {
  return !disabled.value.has(code)
}
function toggleType(code: string, on: boolean): void {
  if (on) disabled.value.delete(code)
  else disabled.value.add(code)
  disabled.value = new Set(disabled.value)
}
async function save(): Promise<void> {
  saving.value = true
  try {
    await store.savePrefs({ email_enabled: emailEnabled.value, disabled_types: [...disabled.value] })
    ElMessage.success('已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await store.loadPrefs()
  emailEnabled.value = store.prefs?.email_enabled ?? true
  disabled.value = new Set(store.prefs?.disabled_types ?? [])
})

defineExpose({ toggleType, save })
</script>

<template>
  <el-form label-width="140px" class="notif-prefs">
    <el-form-item label="邮件通知">
      <el-switch v-model="emailEnabled" />
    </el-form-item>
    <el-form-item v-for="t in NOTIFICATION_TYPES" :key="t.code" :label="t.label">
      <el-switch
        :model-value="isOn(t.code)"
        @update:model-value="(v: string | number | boolean) => toggleType(t.code, Boolean(v))"
      />
    </el-form-item>
    <el-form-item>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </el-form-item>
  </el-form>
</template>

<style scoped>
.notif-prefs { max-width: 480px; }
</style>
