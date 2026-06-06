<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'
import { useAuthStore } from '@/store/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const displayName = computed(() => auth.user?.name || auth.user?.email || '')

async function logout(): Promise<void> {
  auth.logout()
  await router.push({ name: 'login' })
}

async function goProfile(): Promise<void> {
  await router.push({ name: 'account-profile' })
}

async function goChangePassword(): Promise<void> {
  await router.push({ name: 'change-password' })
}

defineExpose({ logout, goProfile })
</script>

<template>
  <el-dropdown v-if="auth.user">
    <span class="user-menu-trigger">{{ displayName }}</span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item data-test="profile" @click="goProfile">{{ t('account.profile') }}</el-dropdown-item>
        <el-dropdown-item data-test="change-password" @click="goChangePassword">{{ t('auth.changeTitle') }}</el-dropdown-item>
        <el-dropdown-item divided data-test="logout" @click="logout">{{ t('auth.logout') }}</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<style scoped>
.user-menu-trigger {
  cursor: pointer;
  padding: 0 8px;
  color: var(--el-text-color-primary);
}
</style>
