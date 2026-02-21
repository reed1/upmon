<script setup lang="ts">
import { computed } from 'vue';
import type { SiteStatus, DayEntry } from '../types';
import SiteCardContent from './SiteCardContent.vue';

const props = defineProps<{
  status: SiteStatus;
  dailySummary: DayEntry[];
  hasAccessLogs: boolean;
}>();

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return 'never';
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function cellColor(value: number | null): string {
  if (value === 1) return 'bg-emerald-500';
  if (value === 0) return 'bg-red-500';
  return 'bg-gray-700';
}

function cellTooltip(value: number | null, hour: number): string {
  const label = `${String(hour).padStart(2, '0')}:00`;
  if (value === 1) return `${label} — up`;
  if (value === 0) return `${label} — down`;
  return `${label} — no data`;
}

function formatDay(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

const sortedDays = computed(() => {
  return [...props.dailySummary].sort((a, b) => b.day.localeCompare(a.day));
});
</script>

<template>
  <router-link
    v-if="hasAccessLogs"
    :to="`/sites/${status.project_id}/${status.site_key}`"
    class="block bg-gray-900 border border-gray-800 border-l-blue-500/60 border-l-2 rounded-lg p-4 transition-colors hover:border-gray-600 hover:border-l-blue-400 cursor-pointer"
  >
    <SiteCardContent
      :status="status"
      :sorted-days="sortedDays"
      :format-day="formatDay"
      :cell-color="cellColor"
      :cell-tooltip="cellTooltip"
      :time-ago="timeAgo"
    />
    <div class="mt-3 flex items-center gap-1.5 text-xs text-gray-500">
      <svg class="size-3.5" viewBox="0 0 16 16" fill="currentColor">
        <path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1H2V3Zm0 3v7a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V6H2Zm3 2h6v1H5V8Zm0 3h4v1H5v-1Z"/>
      </svg>
      <span>Access Logs</span>
      <span>&rarr;</span>
    </div>
  </router-link>
  <div v-else class="bg-gray-900 border border-gray-800 rounded-lg p-4">
    <SiteCardContent
      :status="status"
      :sorted-days="sortedDays"
      :format-day="formatDay"
      :cell-color="cellColor"
      :cell-tooltip="cellTooltip"
      :time-ago="timeAgo"
    />
  </div>
</template>
