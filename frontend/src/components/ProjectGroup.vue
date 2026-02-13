<script setup>
import SiteCard from './SiteCard.vue'

defineProps({
  projectId: { type: String, required: true },
  sites: { type: Array, required: true },
  dailySummary: { type: Object, default: () => ({}) },
})
</script>

<template>
  <section>
    <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
      Project: {{ projectId }}
    </h2>
    <div class="space-y-3">
      <SiteCard
        v-for="site in sites"
        :key="site.site_key"
        :status="site"
        :daily-summary="dailySummary[site.site_key] ?? []"
      />
    </div>
  </section>
</template>
