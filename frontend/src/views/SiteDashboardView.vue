<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { Ref } from 'vue';
import { useRoute } from 'vue-router';
import {
  fetchAccessLogSites,
  fetchAccessLogStats,
  fetchAccessLogEntries,
} from '../api';
import type {
  AccessLogSiteInfo,
  AccessLogStats,
  AccessLogEntries,
} from '../types';

const route = useRoute();
const projectId = route.params.projectId as string;
const siteKey = route.params.siteKey as string;

const stats: Ref<AccessLogStats | null> = ref(null);
const entries: Ref<AccessLogEntries | null> = ref(null);
const loading = ref(true);
const error: Ref<string | null> = ref(null);

function colIndex(columns: string[], name: string): number {
  return columns.indexOf(name);
}

function cell(row: any[], columns: string[], name: string): any {
  const idx = colIndex(columns, name);
  return idx >= 0 ? row[idx] : null;
}

function formatDuration(ms: number | null): string {
  if (ms == null) return '-';
  return `${Math.round(ms)}ms`;
}

function statusColor(code: number): string {
  if (code < 300) return 'text-emerald-400';
  if (code < 400) return 'text-yellow-400';
  return 'text-red-400';
}

onMounted(async () => {
  try {
    const sites = await fetchAccessLogSites();
    const site = sites.find(
      (s: AccessLogSiteInfo) =>
        s.project_id === projectId && s.site_key === siteKey,
    );
    if (!site) throw new Error(`No access log config for ${projectId}/${siteKey}`);

    const [statsData, entriesData] = await Promise.all([
      fetchAccessLogStats(site.config_key),
      fetchAccessLogEntries(site.config_key, 50),
    ]);
    stats.value = statsData;
    entries.value = entriesData;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div>
    <router-link
      to="/"
      class="text-sm text-gray-400 hover:text-gray-200 transition-colors"
    >
      &larr; Back
    </router-link>

    <h2 class="mt-4 text-lg font-bold">
      {{ projectId }} / {{ siteKey }}
      <span class="text-sm font-normal text-gray-500">access logs</span>
    </h2>

    <div
      v-if="error"
      class="mt-4 px-4 py-2 bg-red-900/50 border border-red-700 rounded text-sm text-red-300"
    >
      {{ error }}
    </div>

    <div v-if="loading" class="text-center text-gray-500 py-20">
      Loading...
    </div>

    <template v-else-if="stats">
      <div class="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div
          v-for="(label, idx) in [
            'Total Requests',
            'Avg Duration',
            'Min Duration',
            'Max Duration',
          ]"
          :key="label"
          class="bg-gray-900 border border-gray-800 rounded-lg p-3"
        >
          <div class="text-xs text-gray-500">{{ label }}</div>
          <div class="mt-1 text-lg font-semibold">
            <template v-if="stats.summary.rows.length">
              <template v-if="idx === 0">
                {{ stats.summary.rows[0][idx]?.toLocaleString() ?? '-' }}
              </template>
              <template v-else>
                {{ formatDuration(stats.summary.rows[0][idx]) }}
              </template>
            </template>
            <template v-else>-</template>
          </div>
        </div>
      </div>

      <div
        v-if="stats.status_distribution.rows.length"
        class="mt-6"
      >
        <h3 class="text-sm font-semibold text-gray-400 mb-2">
          Status Codes
        </h3>
        <div class="flex flex-wrap gap-2">
          <div
            v-for="row in stats.status_distribution.rows"
            :key="row[0]"
            class="bg-gray-900 border border-gray-800 rounded px-3 py-1.5 text-sm"
          >
            <span :class="statusColor(row[0])" class="font-mono font-medium">
              {{ row[0] }}
            </span>
            <span class="text-gray-400 ml-2">
              {{ row[1]?.toLocaleString() }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="entries && entries.rows.length" class="mt-6">
        <h3 class="text-sm font-semibold text-gray-400 mb-2">
          Recent Logs
        </h3>
        <div class="overflow-x-auto">
          <table
            class="w-full text-sm border-collapse"
          >
            <thead>
              <tr class="text-left text-gray-500 border-b border-gray-800">
                <th class="py-2 pr-4">Timestamp</th>
                <th class="py-2 pr-4">Method</th>
                <th class="py-2 pr-4">Path</th>
                <th class="py-2 pr-4">Status</th>
                <th class="py-2 pr-4 text-right">Duration</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, i) in entries.rows"
                :key="i"
                class="border-b border-gray-800/50 hover:bg-gray-900/50"
              >
                <td class="py-1.5 pr-4 text-gray-400 whitespace-nowrap">
                  {{ cell(row, entries.columns, 'timestamp') }}
                </td>
                <td class="py-1.5 pr-4 font-mono">
                  {{ cell(row, entries.columns, 'method') }}
                </td>
                <td class="py-1.5 pr-4 text-gray-300 max-w-xs truncate">
                  {{ cell(row, entries.columns, 'path') }}
                </td>
                <td class="py-1.5 pr-4">
                  <span
                    :class="statusColor(cell(row, entries.columns, 'status_code'))"
                    class="font-mono"
                  >
                    {{ cell(row, entries.columns, 'status_code') }}
                  </span>
                </td>
                <td class="py-1.5 pr-4 text-right text-gray-400">
                  {{ formatDuration(cell(row, entries.columns, 'duration_ms')) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
