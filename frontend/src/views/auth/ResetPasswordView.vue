<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { resetPassword } from '@/api/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const token = ref('')
const newPassword = ref('')
const confirm = ref('')
const submitting = ref(false)

onMounted(() => {
  token.value = (route.query.token as string) || ''
})

async function submit(): Promise<void> {
  if (!token.value || !newPassword.value) {
    ElMessage.warning(t('auth.fillAllFields'))
    return
  }
  if (newPassword.value !== confirm.value) {
    ElMessage.warning(t('auth.passwordMismatch'))
    return
  }
  submitting.value = true
  try {
    await resetPassword(token.value, newPassword.value)
    ElMessage.success(t('auth.resetSuccess'))
    await router.push({ name: 'login' })
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.resetFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.resetTitle') }}</h2>
    <el-form @submit.prevent="submit">
      <el-form-item :label="t('auth.resetToken')">
        <el-input v-model="token" data-test="token" />
      </el-form-item>
      <el-form-item :label="t('auth.newPassword')">
        <el-input v-model="newPassword" data-test="new-password" type="password" show-password autocomplete="new-password" />
      </el-form-item>
      <el-form-item :label="t('auth.confirmPassword')">
        <el-input v-model="confirm" data-test="confirm-password" type="password" show-password autocomplete="new-password" @keyup.enter="submit" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.resetSubmit') }}
      </el-button>
      <div class="auth-foot">
        <router-link :to="{ name: 'login' }">{{ t('auth.backToLogin') }}</router-link>
      </div>
    </el-form>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 24px; text-align: center; }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: #888; }
</style>
