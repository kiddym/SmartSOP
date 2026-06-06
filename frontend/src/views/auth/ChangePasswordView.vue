<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { changePassword } from '@/api/auth'
import { errorMessage } from '@/api/http'

const { t } = useI18n()

const oldPassword = ref('')
const newPassword = ref('')
const confirm = ref('')
const submitting = ref(false)

async function submit(): Promise<void> {
  if (!oldPassword.value || !newPassword.value) {
    ElMessage.warning(t('auth.fillAllFields'))
    return
  }
  if (newPassword.value !== confirm.value) {
    ElMessage.warning(t('auth.passwordMismatch'))
    return
  }
  submitting.value = true
  try {
    await changePassword(oldPassword.value, newPassword.value)
    ElMessage.success(t('auth.changeSuccess'))
    oldPassword.value = ''
    newPassword.value = ''
    confirm.value = ''
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.changeFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="change-password-view">
    <el-card class="cp-card">
      <template #header>
        <span>{{ t('auth.changeTitle') }}</span>
      </template>
      <el-form label-width="120px" @submit.prevent="submit">
        <el-form-item :label="t('auth.oldPassword')">
          <el-input v-model="oldPassword" data-test="old-password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item :label="t('auth.newPassword')">
          <el-input v-model="newPassword" data-test="new-password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item :label="t('auth.confirmPassword')">
          <el-input v-model="confirm" data-test="confirm-password" type="password" show-password autocomplete="new-password" @keyup.enter="submit" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" data-test="submit" @click="submit">
            {{ t('auth.changeSubmit') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.change-password-view { padding: 24px; }
.cp-card { max-width: 520px; }
</style>
