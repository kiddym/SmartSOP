<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const companyName = ref('')
const name = ref('')
const email = ref('')
const password = ref('')
const submitting = ref(false)

async function submit(): Promise<void> {
  if (!companyName.value || !name.value || !email.value || password.value.length < 8) {
    ElMessage.warning(t('auth.registerHint'))
    return
  }
  submitting.value = true
  try {
    await auth.register({ company_name: companyName.value, name: name.value, email: email.value, password: password.value })
    await router.push('/')
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.registerFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.register') }}</h2>
    <el-form @submit.prevent="submit">
      <el-form-item :label="t('auth.companyName')">
        <el-input v-model="companyName" data-test="companyName" autocomplete="organization" />
      </el-form-item>
      <el-form-item :label="t('auth.name')">
        <el-input v-model="name" data-test="name" autocomplete="name" />
      </el-form-item>
      <el-form-item :label="t('auth.email')">
        <el-input v-model="email" data-test="email" type="email" autocomplete="email" />
      </el-form-item>
      <el-form-item :label="t('auth.password')">
        <el-input v-model="password" data-test="password" type="password" show-password autocomplete="new-password" @keyup.enter="submit" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.register') }}
      </el-button>
      <div class="auth-foot">
        {{ t('auth.haveAccount') }}
        <router-link :to="{ name: 'login' }">{{ t('auth.login') }}</router-link>
      </div>
    </el-form>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 24px; text-align: center; }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: #888; }
</style>
