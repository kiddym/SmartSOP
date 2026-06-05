<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { usePermission } from '@/composables/usePermission'
import { useBillingStore } from '@/store/billing'

const billing = useBillingStore()
const route = useRoute()
const { hasPermission } = usePermission()

const isCheckoutSuccess = computed(() => route?.query?.checkout === 'success')

onMounted(async () => {
  await billing.loadSubscription()
  if (isCheckoutSuccess.value && billing.subscription) {
    await billing.pollUntilPlanChange(billing.subscription.plan)
  }
})

const sub = computed(() => billing.subscription)
const seatText = computed(() => {
  const s = sub.value
  if (!s) return ''
  return s.seat_limit === null ? `${s.seat_used} / 无限` : `${s.seat_used} / ${s.seat_limit}`
})

async function manage(): Promise<void> {
  await billing.openPortal()
}
</script>

<template>
  <div v-if="sub" class="billing-settings">
    <h2>订阅设置</h2>
    <el-card>
      <p>
        当前套餐：<el-tag>{{ sub.plan }}</el-tag>
      </p>
      <p>订阅状态：{{ sub.subscription_status }}</p>
      <p>席位用量：{{ seatText }}</p>
      <el-progress
        v-if="sub.seat_limit !== null"
        :percentage="Math.min(100, Math.round((sub.seat_used / sub.seat_limit) * 100))"
      />
      <p>已解锁功能：{{ sub.features.join('、') || '无' }}</p>
      <router-link to="/billing/plans">查看套餐对比</router-link>
      <el-button
        v-if="billing.planName === 'pro' && hasPermission('billing.manage')"
        @click="manage"
      >
        管理订阅 / 改支付方式
      </el-button>
      <p v-if="isCheckoutSuccess" class="checkout-hint">
        支付已提交，正在确认订阅状态…
      </p>
    </el-card>
  </div>
</template>
