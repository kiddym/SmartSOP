<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { verifyEmail } from '@/api/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()
const route = useRoute()

const state = ref<'pending' | 'success' | 'failed'>('pending')
const message = ref('')

onMounted(async () => {
  const token = (route.query.token as string) || ''
  if (!token) {
    state.value = 'failed'
    message.value = t('auth.missingToken')
    return
  }
  try {
    await verifyEmail(token)
    state.value = 'success'
  } catch (err) {
    state.value = 'failed'
    message.value = errorMessage(err) ?? t('auth.verifyFailed')
  }
})
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.verifyTitle') }}</h2>
    <div v-if="state === 'pending'" data-test="verify-pending" class="verify-msg">
      {{ t('auth.verifyPending') }}
    </div>
    <el-result
      v-else-if="state === 'success'"
      status="success"
      :title="t('auth.verifySuccess')"
      data-test="verify-success"
    />
    <el-result
      v-else
      status="error"
      :title="message || t('auth.verifyFailed')"
      data-test="verify-failed"
    />
    <div class="auth-foot">
      <router-link :to="{ name: 'login' }">{{ t('auth.backToLogin') }}</router-link>
    </div>
  </AuthLayout>
</template>

<style scoped>
.auth-title {
  margin: 0 0 24px;
  text-align: center;
}
.verify-msg {
  text-align: center;
  color: var(--el-text-color-regular);
}
.auth-foot {
  margin-top: 16px;
  text-align: center;
  font-size: 13px;
  color: #888;
}
</style>
