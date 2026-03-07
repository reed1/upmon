<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import type { Ref } from 'vue';
import { useRoute } from 'vue-router';
import { fetchAccessLogStats, fetchAccessLogEntries } from '../api';
import type { AccessLogStats, AccessLogEntries } from '../types';
import { VueDatePicker } from '@vuepic/vue-datepicker';
import '@vuepic/vue-datepicker/dist/main.css';
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
const selectedExceptionType: Ref<string | null> = ref(null);
const selectedOs: Ref<string | null> = ref(null);
const selectedClientType: Ref<string | null> = ref(null);
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

const dateRange = ref<[Date, Date] | null>(null);

function onDateRangePicked(value: [Date, Date] | null) {
  if (!value) return;
  const [from, to] = value;
  const startOfDay = new Date(
    from.getFullYear(),
    from.getMonth(),
    from.getDate(),
  );
  const dayAfterEnd = new Date(
    to.getFullYear(),
    to.getMonth(),
    to.getDate() + 1,
  );
  onRangeSelect(startOfDay.toISOString(), dayAfterEnd.toISOString());
}

const exceptionTypeConfig = [
  { key: 'none', label: 'OK', colorClass: 'text-emerald-400' },
  { key: 'expected', label: 'Expected', colorClass: 'text-yellow-400' },
  { key: 'unexpected', label: 'Unexpected', colorClass: 'text-red-400' },
] as const;

const exceptionButtons = computed(() => {
  if (!stats.value) return [];
  const countMap = new Map<string, number>();
  for (const row of stats.value.exception_distribution.rows) {
    countMap.set(row[0], row[1]);
  }
  return exceptionTypeConfig.map((cfg) => ({
    ...cfg,
    count: countMap.get(cfg.key) ?? 0,
  }));
});

const osButtons = computed(() => {
  if (!stats.value) return [];
  const rows = stats.value.os_distribution.rows;
  if (
    selectedOs.value != null &&
    !rows.some((r: any[]) => r[0] === selectedOs.value)
  ) {
    return [...rows, [selectedOs.value, 0]];
  }
  return rows;
});

const clientTypeButtons = computed(() => {
  if (!stats.value) return [];
  const rows = stats.value.client_type_distribution.rows;
  if (
    selectedClientType.value != null &&
    !rows.some((r: any[]) => r[0] === selectedClientType.value)
  ) {
    return [...rows, [selectedClientType.value, 0]];
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

function toggleExceptionType(key: string) {
  selectedExceptionType.value =
    selectedExceptionType.value === key ? null : key;
}

function toggleOs(value: string) {
  selectedOs.value = selectedOs.value === value ? null : value;
}

function toggleClientType(value: string) {
  selectedClientType.value = selectedClientType.value === value ? null : value;
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
    exceptionType: selectedExceptionType.value ?? undefined,
    os: selectedOs.value ?? undefined,
    clientType: selectedClientType.value ?? undefined,
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
      f.exceptionType,
      f.os,
      f.clientType,
      f.method,
    ),
    fetchAccessLogEntries(
      projectId,
      siteKey,
      start.value,
      f.end,
      f.exceptionType,
      f.os,
      f.clientType,
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
      f.end,
      f.exceptionType,
      f.os,
      f.clientType,
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

watch(selectedExceptionType, applyFilters);
watch(selectedOs, applyFilters);
watch(selectedClientType, applyFilters);
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
      <VueDatePicker
        v-model="dateRange"
        range
        :enable-time-picker="false"
        dark
        auto-apply
        :max-date="new Date()"
        class="!inline-block !w-auto"
        @update:model-value="onDateRangePicked"
      >
        <template #trigger>
          <button
            class="px-2.5 py-1 text-xs rounded-md border transition-colors bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-600 hover:text-gray-200"
          >
            Custom
          </button>
        </template>
      </VueDatePicker>
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

      <div v-if="exceptionButtons.length" class="mt-6">
        <h3 class="text-sm font-semibold text-gray-400 mb-2">Response Type</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="btn in exceptionButtons"
            :key="btn.key"
            class="rounded px-3 py-1.5 text-sm border transition-colors cursor-pointer"
            :class="
              selectedExceptionType === btn.key
                ? 'bg-gray-700 border-gray-500'
                : 'bg-gray-900 border-gray-800 hover:border-gray-600'
            "
            @click="toggleExceptionType(btn.key)"
          >
            <span :class="btn.colorClass" class="font-medium">
              {{ btn.label }}
            </span>
            <span class="text-gray-400 ml-2">
              {{ btn.count.toLocaleString() }}
            </span>
          </button>
        </div>
      </div>

      <div v-if="osButtons.length" class="mt-6">
        <h3 class="text-sm font-semibold text-gray-400 mb-2">OS</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="row in osButtons"
            :key="row[0]"
            class="rounded px-3 py-1.5 text-sm border transition-colors cursor-pointer"
            :class="
              selectedOs === row[0]
                ? 'bg-gray-700 border-gray-500'
                : 'bg-gray-900 border-gray-800 hover:border-gray-600'
            "
            @click="toggleOs(row[0])"
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

      <div v-if="clientTypeButtons.length" class="mt-6">
        <h3 class="text-sm font-semibold text-gray-400 mb-2">Client Type</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="row in clientTypeButtons"
            :key="row[0]"
            class="rounded px-3 py-1.5 text-sm border transition-colors cursor-pointer"
            :class="
              selectedClientType === row[0]
                ? 'bg-gray-700 border-gray-500'
                : 'bg-gray-900 border-gray-800 hover:border-gray-600'
            "
            @click="toggleClientType(row[0])"
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
