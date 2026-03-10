<script setup lang="ts">
import type { SiteStatus, SiteDailySummary } from '../types';
import SiteCard from './SiteCard.vue';

defineProps<{
  projectId: string;
  sites: SiteStatus[];
  dailySummary: Record<string, SiteDailySummary>;
}>();
</script>

<template>
  <section>
    <h2
      class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3"
    >
      Project: {{ projectId }}
    </h2>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <SiteCard
        v-for="site in sites"
        :key="site.site_key"
        :status="site"
        :site-summary="dailySummary[site.site_key]"
        :has-access-logs="dailySummary[site.site_key]?.has_agent ?? false"
      />
    </div>
  </section>
</template>
