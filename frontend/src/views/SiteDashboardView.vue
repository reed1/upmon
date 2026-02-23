<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import type { Ref } from 'vue';
import { useRoute } from 'vue-router';
import { fetchAccessLogStats, fetchAccessLogEntries } from '../api';
import type { AccessLogStats, AccessLogEntries } from '../types';
import JsonView from '../components/JsonView.vue';

const route = useRoute();
const projectId = route.params.projectId as string;
const siteKey = route.params.siteKey as string;

const periods = [
  { label: '5m', minutes: 5 },
  { label: '10m', minutes: 10 },
  { label: '30m', minutes: 30 },
  { label: '1h', minutes: 1 * 60 },
  { label: '6h', minutes: 6 * 60 },
  { label: '12h', minutes: 12 * 60 },
  { label: '1d', minutes: 24 * 60 },
  { label: '7d', minutes: 7 * 24 * 60 },
  { label: '30d', minutes: 30 * 24 * 60 },
] as const;

const selectedMinutes = ref(30);
const selectedStatus: Ref<number | null> = ref(null);
const stats: Ref<AccessLogStats | null> = ref(null);
const entries: Ref<AccessLogEntries | null> = ref(null);
const loading = ref(true);
const error: Ref<string | null> = ref(null);

function cell(row: any[], columns: string[], name: string): any {
  const idx = columns.indexOf(name);
  return idx >= 0 ? row[idx] : null;
}

function formatTimestamp(utc: string | null): string {
  if (!utc) return '-';
  const d = new Date(utc);
  const day = String(d.getDate()).padStart(2, '0');
  const mon = d.toLocaleString('en-US', { month: 'short' });
  const year = d.getFullYear();
  const time = d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  return `${day} ${mon} ${year} ${time}`;
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

function toggleStatus(code: number) {
  selectedStatus.value = selectedStatus.value === code ? null : code;
}

const expandedRow = ref<number | null>(null);

function toggleRow(i: number) {
  expandedRow.value = expandedRow.value === i ? null : i;
}

function rowToObject(row: any[], columns: string[]): Record<string, unknown> {
  const obj: Record<string, unknown> = {};
  for (let i = 0; i < columns.length; i++) obj[columns[i]] = row[i];
  return obj;
}

async function loadData() {
  expandedRow.value = null;
  loading.value = true;
  error.value = null;
  try {
    const [statsData, entriesData] = await Promise.all([
      fetchAccessLogStats(projectId, siteKey, selectedMinutes.value),
      fetchAccessLogEntries(projectId, siteKey, selectedMinutes.value),
    ]);
    stats.value = statsData;
    entries.value = entriesData;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}

async function loadEntries() {
  expandedRow.value = null;
  try {
    entries.value = await fetchAccessLogEntries(
      projectId,
      siteKey,
      selectedMinutes.value,
      selectedStatus.value ?? undefined,
    );
  } catch (e) {
    error.value = (e as Error).message;
  }
}

watch(selectedMinutes, () => {
  selectedStatus.value = null;
  loadData();
});
watch(selectedStatus, loadEntries);
onMounted(loadData);
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

    <div class="mt-4 flex flex-wrap gap-1.5">
      <button
        v-for="p in periods"
        :key="p.minutes"
        class="px-2.5 py-1 text-xs rounded-md border transition-colors"
        :class="
          selectedMinutes === p.minutes
            ? 'bg-gray-700 border-gray-600 text-gray-100'
            : 'bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-600 hover:text-gray-200'
        "
        @click="selectedMinutes = p.minutes"
      >
        {{ p.label }}
      </button>
    </div>

    <div
      v-if="error"
      class="mt-4 px-4 py-2 bg-red-900/50 border border-red-700 rounded text-sm text-red-300"
    >
      {{ error }}
    </div>

    <div v-if="loading" class="text-center text-gray-500 py-20">Loading...</div>

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

      <div v-if="stats.status_distribution.rows.length" class="mt-6">
        <h3 class="text-sm font-semibold text-gray-400 mb-2">Status Codes</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="row in stats.status_distribution.rows"
            :key="row[0]"
            class="rounded px-3 py-1.5 text-sm border transition-colors cursor-pointer"
            :class="
              selectedStatus === row[0]
                ? 'bg-gray-700 border-gray-500'
                : 'bg-gray-900 border-gray-800 hover:border-gray-600'
            "
            @click="toggleStatus(row[0])"
          >
            <span :class="statusColor(row[0])" class="font-mono font-medium">
              {{ row[0] }}
            </span>
            <span class="text-gray-400 ml-2">
              {{ row[1]?.toLocaleString() }}
            </span>
          </button>
        </div>
      </div>

      <div v-if="entries && entries.rows.length" class="mt-6">
        <h3 class="text-sm font-semibold text-gray-400 mb-2">Recent Logs</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm border-collapse">
            <thead>
              <tr class="text-left text-gray-500 border-b border-gray-800">
                <th class="py-2 w-6"></th>
                <th class="py-2 pr-4">Timestamp</th>
                <th class="py-2 pr-4">Method</th>
                <th class="py-2 pr-4">Path</th>
                <th class="py-2 pr-4">Status</th>
                <th class="py-2 pr-4 text-right">Duration</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(row, i) in entries.rows" :key="i">
                <tr
                  class="border-b border-gray-800/50 hover:bg-gray-900/50 cursor-pointer"
                  @click="toggleRow(i)"
                >
                  <td class="py-1.5 pr-1 text-gray-600 text-xs w-6">
                    <span
                      class="inline-block transition-transform"
                      :class="expandedRow === i ? 'rotate-90' : ''"
                      >&#9656;</span
                    >
                  </td>
                  <td class="py-1.5 pr-4 text-gray-400 whitespace-nowrap">
                    {{
                      formatTimestamp(cell(row, entries.columns, 'timestamp'))
                    }}
                  </td>
                  <td class="py-1.5 pr-4 font-mono">
                    {{ cell(row, entries.columns, 'method') }}
                  </td>
                  <td class="py-1.5 pr-4 text-gray-300 max-w-xs truncate">
                    {{ cell(row, entries.columns, 'path') }}
                  </td>
                  <td class="py-1.5 pr-4">
                    <span
                      :class="
                        statusColor(cell(row, entries.columns, 'status_code'))
                      "
                      class="font-mono"
                    >
                      {{ cell(row, entries.columns, 'status_code') }}
                    </span>
                  </td>
                  <td class="py-1.5 pr-4 text-right text-gray-400">
                    {{
                      formatDuration(cell(row, entries.columns, 'duration_ms'))
                    }}
                  </td>
                </tr>
                <tr v-if="expandedRow === i">
                  <td
                    colspan="6"
                    class="px-4 py-3 bg-gray-950 border-b border-gray-800"
                  >
                    <JsonView :data="rowToObject(row, entries.columns)" />
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
