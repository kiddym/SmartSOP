<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { usePermission } from '@/composables/usePermission'
import { useBillingStore } from '@/store/billing'

const billing = useBillingStore()
const { hasPermission } = usePermission()
const salesEmail = import.meta.env.VITE_SALES_CONTACT_EMAIL ?? ''

onMounted(() => {
  if (!billing.subscription) billing.loadSubscription()
})

const catalog = computed(() => billing.subscription?.catalog ?? [])
const currentPlan = computed(() => billing.planName)
const busy = ref(false)

function seatLabel(limit: number | null): string {
  return limit === null ? '无限席位' : `${limit} 个席位`
}

async function subscribe(): Promise<void> {
  busy.value = true
  try {
    await billing.startCheckout()
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="plans-view">
    <h2>订阅套餐</h2>
    <div class="plan-grid">
      <el-card
        v-for="entry in catalog"
        :key="entry.plan"
        :class="{ current: entry.plan === currentPlan }"
      >
        <h3>{{ entry.plan }}</h3>
        <p>{{ seatLabel(entry.seat_limit) }}</p>
        <ul>
          <li v-for="f in entry.features" :key="f">{{ f }}</li>
        </ul>
        <el-tag v-if="entry.plan === currentPlan" type="success">当前套餐</el-tag>
        <template v-else>
          <el-button
            v-if="entry.plan === 'pro' && hasPermission('billing.manage')"
            type="primary"
            :loading="busy"
            :disabled="busy"
            @click="subscribe"
          >
            订阅
          </el-button>
          <template v-else-if="entry.plan === 'enterprise'">
            <el-button v-if="salesEmail" tag="a" :href="`mailto:${salesEmail}`">
              联系销售
            </el-button>
            <el-button v-else disabled>联系销售</el-button>
          </template>
          <el-button v-else disabled>请联系管理员升级</el-button>
        </template>
      </el-card>
    </div>
  </div>
</template>
