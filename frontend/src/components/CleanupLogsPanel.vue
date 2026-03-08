<script setup lang="ts">
import { ref } from 'vue';
import type { CleanupLogEntry } from '../types';

defineProps<{
  logs: CleanupLogEntry[];
}>();

const open = ref(false);

function formatTime(iso: string): string {
  const d = new Date(iso);
  const mon = d.toLocaleString('en-US', { month: 'short' });
  const day = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${mon} ${day} ${hh}:${mm}`;
}
</script>

<template>
  <div>
    <button
      class="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors cursor-pointer"
      @click="open = !open"
    >
      <svg
        class="w-3.5 h-3.5 transition-transform"
        :class="open ? 'rotate-90' : ''"
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fill-rule="evenodd"
          d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
          clip-rule="evenodd"
        />
      </svg>
      Cleanup Logs
    </button>

    <div v-if="open" class="mt-2 overflow-x-auto">
      <table class="w-full text-sm border-collapse">
        <thead>
          <tr class="text-gray-500 border-b border-gray-800 text-left">
            <th class="px-3 py-2">Time</th>
            <th class="px-3 py-2">Retention</th>
            <th class="px-3 py-2">Status</th>
            <th class="px-3 py-2">Deleted</th>
            <th class="px-3 py-2 text-right">Duration</th>
            <th class="px-3 py-2">Error</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="log in logs"
            :key="log.id"
            class="border-b border-gray-800/50 hover:bg-gray-900/50"
          >
            <td class="px-3 py-2 whitespace-nowrap">
              {{ formatTime(log.executed_at) }}
            </td>
            <td class="px-3 py-2">{{ log.retention_days }}d</td>
            <td class="px-3 py-2">
              <span
                :class="
                  log.error_message ? 'text-red-400' : 'text-emerald-400'
                "
              >
                {{ log.status_code ?? '-' }}
              </span>
            </td>
            <td class="px-3 py-2">{{ log.deleted_count ?? '-' }}</td>
            <td class="px-3 py-2 text-right">{{ log.duration_ms }}ms</td>
            <td class="px-3 py-2 max-w-xs truncate text-red-400">
              {{ log.error_message ?? '' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
