<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElDropdown, ElDropdownItem, ElDropdownMenu, ElDialog, ElMessage } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import { listSwitchableAccounts } from '@/api/auth'
import { errorMessage } from '@/api/http'
import type { SwitchableAccount } from '@/types/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const displayName = computed(() => auth.user?.name || auth.user?.email || '')

const switchable = ref<SwitchableAccount[]>([])
const showSwitch = ref(false)
const switching = ref(false)

async function loadSwitchable(): Promise<void> {
  try {
    switchable.value = await listSwitchableAccounts()
  } catch {
    // 静默：普通用户无此能力时返回空列表，请求失败也仅隐藏入口
    switchable.value = []
  }
}

async function logout(): Promise<void> {
  await auth.logout()
  await router.push({ name: 'login' })
}

async function goProfile(): Promise<void> {
  await router.push({ name: 'account-profile' })
}

async function goChangePassword(): Promise<void> {
  await router.push({ name: 'change-password' })
}

function openSwitch(): void {
  showSwitch.value = true
}

async function doSwitch(companyId: string): Promise<void> {
  switching.value = true
  try {
    await auth.switchAccount(companyId)
    showSwitch.value = false
    ElMessage.success(t('auth.switchSuccess'))
    await router.push({ path: '/' })
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.switchFailed'))
  } finally {
    switching.value = false
  }
}

onMounted(loadSwitchable)

defineExpose({ logout, goProfile })
</script>

<template>
  <el-dropdown v-if="auth.user">
    <span class="user-menu-trigger">{{ displayName }}</span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item data-test="profile" @click="goProfile">{{ t('account.profile') }}</el-dropdown-item>
        <el-dropdown-item data-test="change-password" @click="goChangePassword">{{ t('auth.changeTitle') }}</el-dropdown-item>
        <el-dropdown-item v-if="switchable.length" data-test="switch-account" @click="openSwitch">{{ t('auth.switchAccount') }}</el-dropdown-item>
        <el-dropdown-item divided data-test="logout" @click="logout">{{ t('auth.logout') }}</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <el-dialog v-model="showSwitch" :title="t('auth.switchAccountTitle')" width="420px">
    <p class="switch-hint">{{ t('auth.switchAccountHint') }}</p>
    <div class="switch-list">
      <el-button
        v-for="acc in switchable"
        :key="acc.company_id"
        class="switch-item"
        :loading="switching"
        data-test="switch-item"
        @click="doSwitch(acc.company_id)"
      >
        {{ acc.company_name }}
      </el-button>
    </div>
  </el-dialog>
</template>

<style scoped>
.user-menu-trigger {
  cursor: pointer;
  padding: 0 8px;
  color: var(--el-text-color-primary);
}
.switch-hint {
  margin: 0 0 12px;
  color: var(--el-text-color-regular);
  font-size: 13px;
}
.switch-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.switch-item {
  justify-content: flex-start;
  width: 100%;
  margin-left: 0;
}
</style>
