<script setup lang="ts">
import type { FrontendErrorStats } from '../types';

const props = defineProps<{
  topErrors: FrontendErrorStats['top_errors'];
  selectedFingerprint: string | null;
}>();

const emit = defineEmits<{
  select: [fingerprint: string];
}>();

function cell(row: any[], name: string): any {
  const idx = props.topErrors.columns.indexOf(name);
  return idx >= 0 ? row[idx] : null;
}

function formatLastSeen(epochSec: number | null): string {
  if (epochSec == null) return '-';
  const seconds = Math.floor(Date.now() / 1000) - epochSec;
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}
</script>

<template>
  <div>
    <h3 class="text-sm font-semibold text-gray-400 mb-2">
      Top Errors
      <span class="font-normal text-gray-600">
        — grouped by fingerprint, most frequent first
      </span>
    </h3>
    <div class="overflow-x-auto">
      <table class="w-full text-sm border-collapse">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-800">
            <th class="py-2 pr-4">Error</th>
            <th class="py-2 pr-4">Page</th>
            <th class="py-2 pr-4 text-right">Count</th>
            <th class="py-2 pr-4 text-right">Sessions</th>
            <th class="py-2 pr-4 text-right whitespace-nowrap">Last seen</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in topErrors.rows"
            :key="cell(row, 'fingerprint')"
            class="border-b border-gray-800/50 hover:bg-gray-900/50 cursor-pointer"
            :class="
              selectedFingerprint === cell(row, 'fingerprint')
                ? 'bg-gray-800/60'
                : ''
            "
            @click="emit('select', cell(row, 'fingerprint'))"
          >
            <td class="py-1.5 pr-4 max-w-md">
              <div class="font-mono text-red-400 truncate">
                {{ cell(row, 'error_class') ?? cell(row, 'kind') }}
              </div>
              <div class="text-gray-400 truncate">
                {{ cell(row, 'message') }}
              </div>
            </td>
            <td class="py-1.5 pr-4 text-gray-500 max-w-xs truncate">
              {{ cell(row, 'page_url') }}
            </td>
            <td class="py-1.5 pr-4 text-right font-semibold">
              {{ cell(row, 'count')?.toLocaleString() }}
            </td>
            <td class="py-1.5 pr-4 text-right text-gray-400">
              {{ cell(row, 'sessions')?.toLocaleString() }}
            </td>
            <td class="py-1.5 pr-4 text-right text-gray-500 whitespace-nowrap">
              {{ formatLastSeen(cell(row, 'last_seen')) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="mt-2 text-xs text-gray-600">
      Each distinct error is reported once per page load, so Count is broken
      page loads — not retries within one.
    </p>
  </div>
</template>
