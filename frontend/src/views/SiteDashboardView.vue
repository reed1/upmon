<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { Ref } from 'vue';
import { useRoute } from 'vue-router';
import { fetchAccessLogStats, fetchAccessLogEntries } from '../api';
import type { AccessLogStats, AccessLogEntries } from '../types';
import JsonView from '../components/JsonView.vue';
import VolumeChart from '../components/VolumeChart.vue';

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
const selectedMethod: Ref<string | null> = ref(null);
const customStart: Ref<string | null> = ref(null);
const customEnd: Ref<string | null> = ref(null);
const stats: Ref<AccessLogStats | null> = ref(null);
const entries: Ref<AccessLogEntries | null> = ref(null);
const loading = ref(true);
const error: Ref<string | null> = ref(null);

const customRangeLabel = computed(() => {
  if (!customStart.value || !customEnd.value) return null;
  const fmt = (iso: string) => {
    const d = new Date(iso);
    const mon = d.toLocaleString('en-US', { month: 'short' });
    const day = d.getDate();
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${mon} ${day} ${hh}:${mm}`;
  };
  return `${fmt(customStart.value)} \u2013 ${fmt(customEnd.value)}`;
});

const effectiveSpanMinutes = computed(() => {
  if (customStart.value && customEnd.value) {
    return (
      (new Date(customEnd.value).getTime() -
        new Date(customStart.value).getTime()) /
      60000
    );
  }
  return selectedMinutes.value;
});

function onVolumeSelect(start: string, end: string) {
  customStart.value = start;
  customEnd.value = end;
  loadData();
}

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

function toggleMethod(method: string) {
  selectedMethod.value = selectedMethod.value === method ? null : method;
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

function clearCustomRange() {
  customStart.value = null;
  customEnd.value = null;
  loadData();
}

async function loadData() {
  expandedRow.value = null;
  loading.value = true;
  error.value = null;
  try {
    const start =
      customStart.value ??
      new Date(Date.now() - selectedMinutes.value * 60_000).toISOString();
    const end = customEnd.value ?? undefined;
    const [statsData, entriesData] = await Promise.all([
      fetchAccessLogStats(projectId, siteKey, start, end),
      fetchAccessLogEntries(projectId, siteKey, start, undefined, end),
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
    const start =
      customStart.value ??
      new Date(Date.now() - selectedMinutes.value * 60_000).toISOString();
    const end = customEnd.value ?? undefined;
    entries.value = await fetchAccessLogEntries(
      projectId,
      siteKey,
      start,
      selectedStatus.value ?? undefined,
      end,
      selectedMethod.value ?? undefined,
    );
  } catch (e) {
    error.value = (e as Error).message;
  }
}

watch(selectedMinutes, () => {
  customStart.value = null;
  customEnd.value = null;
  selectedStatus.value = null;
  selectedMethod.value = null;
  loadData();
});
watch(selectedStatus, loadEntries);
watch(selectedMethod, loadEntries);
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
      v-if="customRangeLabel"
      class="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md bg-blue-900/50 border border-blue-700 text-blue-200"
    >
      <span>{{ customRangeLabel }}</span>
      <button
        class="ml-1 hover:text-white transition-colors cursor-pointer"
        @click="clearCustomRange"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
          <path
            d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
          />
        </svg>
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

      <VolumeChart
        v-if="stats.volume?.rows?.length"
        class="mt-6"
        :rows="stats.volume.rows"
        :span-minutes="effectiveSpanMinutes"
        @select="onVolumeSelect"
      />

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

      <div v-if="stats.method_distribution.rows.length" class="mt-6">
        <h3 class="text-sm font-semibold text-gray-400 mb-2">Request Method</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="row in stats.method_distribution.rows"
            :key="row[0]"
            class="rounded px-3 py-1.5 text-sm border transition-colors cursor-pointer"
            :class="
              selectedMethod === row[0]
                ? 'bg-gray-700 border-gray-500'
                : 'bg-gray-900 border-gray-800 hover:border-gray-600'
            "
            @click="toggleMethod(row[0])"
          >
            <span class="font-mono font-medium">
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
                  <td class="py-1.5 pr-1 w-6">
                    <svg
                      class="w-4 h-4 text-gray-400 transition-transform duration-150"
                      :class="expandedRow === i ? 'rotate-90' : ''"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                    >
                      <path
                        fill-rule="evenodd"
                        d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                        clip-rule="evenodd"
                      />
                    </svg>
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
