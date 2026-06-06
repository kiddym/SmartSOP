<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const token = ref('')
const name = ref('')
const password = ref('')
const submitting = ref(false)

onMounted(() => {
  token.value = (route.query.token as string) || ''
  if (!token.value) ElMessage.warning(t('auth.missingToken'))
})

async function submit(): Promise<void> {
  if (!token.value || !name.value || !password.value) {
    ElMessage.warning(t('auth.fillAllFields'))
    return
  }
  submitting.value = true
  try {
    await auth.acceptInvite(token.value, name.value, password.value)
    await router.push('/')
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.acceptFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.acceptTitle') }}</h2>
    <p class="auth-hint">{{ t('auth.acceptHint') }}</p>
    <el-form @submit.prevent="submit">
      <el-form-item :label="t('auth.name')">
        <el-input v-model="name" data-test="name" autocomplete="name" />
      </el-form-item>
      <el-form-item :label="t('auth.password')">
        <el-input v-model="password" data-test="password" type="password" show-password autocomplete="new-password" @keyup.enter="submit" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.acceptSubmit') }}
      </el-button>
      <div class="auth-foot">
        <router-link :to="{ name: 'login' }">{{ t('auth.backToLogin') }}</router-link>
      </div>
    </el-form>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 16px; text-align: center; }
.auth-hint { margin: 0 0 20px; text-align: center; font-size: 13px; color: #888; }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: #888; }
</style>
