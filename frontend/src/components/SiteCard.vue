<script setup lang="ts">
import { computed } from 'vue';
import type { SiteStatus, DayEntry } from '../types';

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
  <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
    <div class="flex items-center justify-between gap-4">
      <div class="flex items-center gap-2 min-w-0">
        <span
          class="shrink-0 size-2.5 rounded-full"
          :class="status.is_up ? 'bg-emerald-500' : 'bg-red-500'"
        />
        <router-link
          v-if="hasAccessLogs"
          :to="`/sites/${status.project_id}/${status.site_key}`"
          class="font-medium truncate hover:text-white transition-colors"
        >
          {{ status.site_key }}
        </router-link>
        <span v-else class="font-medium truncate">{{ status.site_key }}</span>
      </div>
      <div class="flex items-center gap-4 text-sm text-gray-400 shrink-0">
        <span v-if="status.response_ms != null"
          >{{ status.response_ms }}ms</span
        >
        <span>{{ timeAgo(status.last_checked_at) }}</span>
      </div>
    </div>

    <div class="mt-1 text-sm text-gray-500 truncate">{{ status.url }}</div>

    <div v-if="status.error_message" class="mt-2 text-sm text-red-400">
      {{ status.error_message }}
    </div>

    <div v-if="sortedDays.length" class="mt-3 space-y-1">
      <div
        v-for="entry in sortedDays"
        :key="entry.day"
        class="flex items-center gap-2"
      >
        <span class="text-xs text-gray-500 w-16 shrink-0 text-right">{{
          formatDay(entry.day)
        }}</span>
        <div class="flex gap-px items-end">
          <div
            v-for="(val, hour) in entry.checks"
            :key="hour"
            class="w-1 h-3 rounded-sm"
            :class="cellColor(val)"
            :title="cellTooltip(val, hour)"
          />
        </div>
      </div>
    </div>
  </div>
</template>
