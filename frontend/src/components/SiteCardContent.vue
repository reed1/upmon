<script setup lang="ts">
import type { SiteStatus, DayEntry } from '../types';

defineProps<{
  status: SiteStatus;
  sortedDays: DayEntry[];
  formatDay: (dateStr: string) => string;
  cellColor: (value: number | null) => string;
  cellTooltip: (value: number | null, hour: number) => string;
  timeAgo: (dateStr: string | null) => string;
}>();
</script>

<template>
  <div class="flex items-center justify-between gap-4">
    <div class="flex items-center gap-2 min-w-0">
      <span
        class="shrink-0 size-2.5 rounded-full"
        :class="status.is_up ? 'bg-emerald-500' : 'bg-red-500'"
      />
      <span class="font-medium truncate">{{ status.site_key }}</span>
    </div>
    <div class="flex items-center gap-4 text-sm text-gray-400 shrink-0">
      <span v-if="status.response_ms != null">{{ status.response_ms }}ms</span>
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
</template>
