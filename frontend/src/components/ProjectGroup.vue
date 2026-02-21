<script setup lang="ts">
import type { SiteStatus, DayEntry, AccessLogSiteInfo } from '../types';
import SiteCard from './SiteCard.vue';

defineProps<{
  projectId: string;
  sites: SiteStatus[];
  dailySummary: Record<string, DayEntry[]>;
  accessLogSites: AccessLogSiteInfo[];
}>();
</script>

<template>
  <section>
    <h2
      class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3"
    >
      Project: {{ projectId }}
    </h2>
    <div class="space-y-3">
      <SiteCard
        v-for="site in sites"
        :key="site.site_key"
        :status="site"
        :daily-summary="dailySummary[site.site_key] ?? []"
        :has-access-logs="
          accessLogSites.some(
            (a) =>
              a.project_id === site.project_id && a.site_key === site.site_key,
          )
        "
      />
    </div>
  </section>
</template>
