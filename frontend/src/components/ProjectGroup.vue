<script setup lang="ts">
import type { SiteStatus, DayEntry } from '../types';
import SiteCard from './SiteCard.vue';

defineProps<{
  projectId: string;
  sites: SiteStatus[];
  dailySummary: Record<string, DayEntry[]>;
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
      />
    </div>
  </section>
</template>
