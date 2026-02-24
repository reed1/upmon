<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { Ref } from 'vue';
import { useRoute } from 'vue-router';
import { fetchAccessLogStats, fetchAccessLogEntries } from '../api';
import type { AccessLogStats, AccessLogEntries } from '../types';
import VolumeChart from '../components/VolumeChart.vue';
import LogEntriesTable from '../components/LogEntriesTable.vue';

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
const start = ref(new Date(Date.now() - 30 * 60_000).toISOString());
const end: Ref<string | null> = ref(null);
const stats: Ref<AccessLogStats | null> = ref(null);
const entries: Ref<AccessLogEntries | null> = ref(null);
const loading = ref(true);
const error: Ref<string | null> = ref(null);

const rangeLabel = computed(() => {
  if (!end.value) return null;
  const fmt = (iso: string) => {
    const d = new Date(iso);
    const mon = d.toLocaleString('en-US', { month: 'short' });
    const day = d.getDate();
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${mon} ${day} ${hh}:${mm}`;
  };
  return `${fmt(start.value)} \u2013 ${fmt(end.value)}`;
});

const effectiveSpanMinutes = computed(() => {
  if (end.value) {
    return (
      (new Date(end.value).getTime() - new Date(start.value).getTime()) / 60000
    );
  }
  return selectedMinutes.value;
});

function selectPeriod(minutes: number) {
  selectedMinutes.value = minutes;
  start.value = new Date(Date.now() - minutes * 60_000).toISOString();
  end.value = null;
  loadData();
}

function onRangeSelect(rangeStart: string, rangeEnd: string) {
  start.value = rangeStart;
  end.value = rangeEnd;
  loadData();
}

const statusButtons = computed(() => {
  if (!stats.value) return [];
  const rows = stats.value.status_distribution.rows;
  if (
    selectedStatus.value != null &&
    !rows.some((r) => r[0] === selectedStatus.value)
  ) {
    return [...rows, [selectedStatus.value, 0]].sort((a, b) => a[0] - b[0]);
  }
  return rows;
});

const methodButtons = computed(() => {
  if (!stats.value) return [];
  const rows = stats.value.method_distribution.rows;
  if (
    selectedMethod.value != null &&
    !rows.some((r) => r[0] === selectedMethod.value)
  ) {
    return [...rows, [selectedMethod.value, 0]];
  }
  return rows;
});

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

const sortColumn = ref('epoch_sec');
const sortDir = ref<'asc' | 'desc'>('desc');

function onSort(column: string, dir: 'asc' | 'desc') {
  sortColumn.value = column;
  sortDir.value = dir;
  reloadLogEntries();
}

function clearRange() {
  start.value = new Date(
    Date.now() - selectedMinutes.value * 60_000,
  ).toISOString();
  end.value = null;
  loadData();
}

function filterParams() {
  return {
    statusCode: selectedStatus.value ?? undefined,
    method: selectedMethod.value ?? undefined,
    end: end.value ?? undefined,
  };
}

async function fetchAll() {
  const f = filterParams();
  const [statsData, entriesData] = await Promise.all([
    fetchAccessLogStats(
      projectId,
      siteKey,
      start.value,
      f.end,
      f.statusCode,
      f.method,
    ),
    fetchAccessLogEntries(
      projectId,
      siteKey,
      start.value,
      f.statusCode,
      f.end,
      f.method,
      sortColumn.value,
      sortDir.value,
    ),
  ]);
  stats.value = statsData;
  entries.value = entriesData;
}

async function reloadLogEntries() {
  try {
    const f = filterParams();
    entries.value = await fetchAccessLogEntries(
      projectId,
      siteKey,
      start.value,
      f.statusCode,
      f.end,
      f.method,
      sortColumn.value,
      sortDir.value,
    );
  } catch (e) {
    error.value = (e as Error).message;
  }
}

async function loadData() {
  loading.value = true;
  error.value = null;
  try {
    await fetchAll();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}

async function applyFilters() {
  try {
    await fetchAll();
  } catch (e) {
    error.value = (e as Error).message;
  }
}

watch(selectedStatus, applyFilters);
watch(selectedMethod, applyFilters);
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
        @click="selectPeriod(p.minutes)"
      >
        {{ p.label }}
      </button>
    </div>

    <div
      v-if="rangeLabel"
      class="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md bg-blue-900/50 border border-blue-700 text-blue-200"
    >
      <span>{{ rangeLabel }}</span>
      <button
        class="ml-1 hover:text-white transition-colors cursor-pointer"
        @click="clearRange"
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
        @select="onRangeSelect"
      />

      <div v-if="statusButtons.length" class="mt-6">
        <h3 class="text-sm font-semibold text-gray-400 mb-2">Status Codes</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="row in statusButtons"
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

      <div v-if="methodButtons.length" class="mt-6">
        <h3 class="text-sm font-semibold text-gray-400 mb-2">Request Method</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="row in methodButtons"
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

      <LogEntriesTable
        v-if="entries && entries.rows.length"
        class="mt-6"
        :entries="entries"
        :sort-column="sortColumn"
        :sort-dir="sortDir"
        @sort="onSort"
      />
    </template>
  </div>
</template>
