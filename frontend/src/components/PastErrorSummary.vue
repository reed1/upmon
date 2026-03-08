<script setup lang="ts">
import { ref, computed } from 'vue';
import type { DailyErrorCount } from '../types';

const props = defineProps<{
  entries: DailyErrorCount[];
}>();

const open = ref(false);

const hasErrors = computed(() =>
  props.entries.some((e) => e.error_count != null && e.error_count > 0),
);

if (hasErrors.value) open.value = true;

function formatDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  const day = String(d.getDate()).padStart(2, '0');
  const mon = d.toLocaleString('en-US', { month: 'short' });
  const year = d.getFullYear();
  return `${day} ${mon} ${year}`;
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
      Past Error Summary
    </button>

    <div v-if="open" class="mt-2 overflow-x-auto">
      <table class="w-full text-sm border-collapse">
        <thead>
          <tr class="text-gray-500 border-b border-gray-800 text-left">
            <th class="px-3 py-2">Date</th>
            <th class="px-3 py-2 text-right">Error Count</th>
            <th class="px-3 py-2">Error</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="entry in entries"
            :key="entry.date"
            class="border-b border-gray-800/50 hover:bg-gray-900/50"
          >
            <td class="px-3 py-2 whitespace-nowrap">
              {{ formatDate(entry.date) }}
            </td>
            <td class="px-3 py-2 text-right">
              <span
                :class="
                  entry.error_count != null && entry.error_count > 0
                    ? 'text-red-400'
                    : 'text-emerald-400'
                "
              >
                {{ entry.error_count ?? '-' }}
              </span>
            </td>
            <td class="px-3 py-2 max-w-xs truncate text-red-400">
              {{ entry.agent_error ?? '' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
