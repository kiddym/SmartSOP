<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useBillingStore } from '@/store/billing'

const billing = useBillingStore()

onMounted(() => {
  if (!billing.subscription) billing.loadSubscription()
})

const catalog = computed(() => billing.subscription?.catalog ?? [])
const currentPlan = computed(() => billing.planName)

function seatLabel(limit: number | null): string {
  return limit === null ? '无限席位' : `${limit} 个席位`
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
        <el-button v-else disabled>请联系管理员升级</el-button>
      </el-card>
    </div>
  </div>
</template>
