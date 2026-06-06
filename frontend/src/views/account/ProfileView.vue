<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { getMyProfile, updateMyProfile } from '@/api/users'
import { errorMessage } from '@/api/http'
import { useAuthStore } from '@/store/auth'
import type { UserRead } from '@/types/platform'

const { t } = useI18n()
const auth = useAuthStore()

const loading = ref(false)
const submitting = ref(false)
const profile = ref<UserRead | null>(null)

const form = reactive({
  name: '',
  phone: '',
  job_title: '',
  avatar_url: '',
  locale: '',
})

function applyForm(u: UserRead): void {
  profile.value = u
  form.name = u.name ?? ''
  form.phone = u.phone ?? ''
  form.job_title = u.job_title ?? ''
  form.avatar_url = u.avatar_url ?? ''
  form.locale = u.locale ?? ''
}

async function load(): Promise<void> {
  loading.value = true
  try {
    applyForm(await getMyProfile())
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('account.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function submit(): Promise<void> {
  if (!form.name.trim()) {
    ElMessage.warning(t('account.nameRequired'))
    return
  }
  submitting.value = true
  try {
    const updated = await updateMyProfile({
      name: form.name.trim(),
      phone: form.phone.trim() || null,
      job_title: form.job_title.trim() || null,
      avatar_url: form.avatar_url.trim() || null,
      locale: form.locale || undefined,
    })
    applyForm(updated)
    // 同步顶栏显示名等：刷新 auth store 的 user。
    await auth.loadMe()
    ElMessage.success(t('account.saveSuccess'))
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('account.saveFailed'))
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="profile-view" v-loading="loading">
    <el-card class="profile-card">
      <template #header>
        <span>{{ t('account.profileTitle') }}</span>
      </template>

      <div class="avatar-row">
        <el-avatar :size="64" :src="form.avatar_url || undefined" data-test="avatar">
          {{ (form.name || profile?.email || '?').slice(0, 1).toUpperCase() }}
        </el-avatar>
      </div>

      <el-form label-width="120px" @submit.prevent="submit">
        <el-form-item :label="t('account.email')">
          <el-input :model-value="profile?.email ?? ''" data-test="email" disabled />
        </el-form-item>
        <el-form-item :label="t('account.name')">
          <el-input v-model="form.name" data-test="name" maxlength="128" />
        </el-form-item>
        <el-form-item :label="t('account.phone')">
          <el-input v-model="form.phone" data-test="phone" maxlength="40" />
        </el-form-item>
        <el-form-item :label="t('account.jobTitle')">
          <el-input v-model="form.job_title" data-test="job-title" maxlength="128" />
        </el-form-item>
        <el-form-item :label="t('account.locale')">
          <el-select v-model="form.locale" data-test="locale">
            <el-option label="简体中文" value="zh-CN" />
            <el-option label="English" value="en-US" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('account.avatarUrl')">
          <el-input v-model="form.avatar_url" data-test="avatar-url" maxlength="512" />
        </el-form-item>
        <el-form-item :label="t('account.rate')">
          <el-input :model-value="profile?.rate ?? '—'" data-test="rate" disabled />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" data-test="submit" @click="submit">
            {{ t('common.save') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.profile-view {
  padding: 24px;
}
.profile-card {
  max-width: 560px;
}
.avatar-row {
  margin-bottom: 16px;
}
</style>
