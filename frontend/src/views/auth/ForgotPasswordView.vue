<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { forgotPassword } from '@/api/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()

const email = ref('')
const companySlug = ref('')
const submitting = ref(false)
const sent = ref(false)

async function submit(): Promise<void> {
  if (!email.value) {
    ElMessage.warning(t('auth.fillEmailPassword'))
    return
  }
  submitting.value = true
  try {
    await forgotPassword(email.value, companySlug.value)
    sent.value = true
    ElMessage.success(t('auth.forgotSent'))
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.registerFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.forgotTitle') }}</h2>
    <p v-if="!sent" class="auth-hint">{{ t('auth.forgotHint') }}</p>
    <p v-else class="auth-hint">{{ t('auth.forgotSent') }}</p>
    <el-form v-if="!sent" @submit.prevent="submit">
      <el-form-item :label="t('auth.email')">
        <el-input v-model="email" data-test="email" type="email" autocomplete="username" />
      </el-form-item>
      <el-form-item :label="t('auth.companySlugOptional')">
        <el-input v-model="companySlug" data-test="company-slug" @keyup.enter="submit" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.sendResetLink') }}
      </el-button>
    </el-form>
    <div class="auth-foot">
      <router-link :to="{ name: 'login' }">{{ t('auth.backToLogin') }}</router-link>
    </div>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 16px; text-align: center; }
.auth-hint { margin: 0 0 20px; text-align: center; font-size: 13px; color: #888; }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: #888; }
</style>
