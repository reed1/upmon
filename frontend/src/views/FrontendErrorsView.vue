<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue';
import type { Ref } from 'vue';
import { useRoute } from 'vue-router';
import {
  fetchFrontendErrorStats,
  fetchFrontendErrors,
  fetchFrontendErrorPage,
} from '../api';
import type { FrontendErrorFilters } from '../api';
import type { FrontendErrorStats, FrontendErrorEntries } from '../types';
import SiteTabs from '../components/SiteTabs.vue';
import PeriodSelector from '../components/PeriodSelector.vue';
import VolumeChart from '../components/VolumeChart.vue';
import TopErrorsPanel from '../components/TopErrorsPanel.vue';
import FrontendErrorTable from '../components/FrontendErrorTable.vue';

const route = useRoute();
const projectId = route.params.projectId as string;
const siteKey = route.params.siteKey as string;

const selectedMinutes = ref(24 * 60);
// One object rather than four refs so the filter chip groups can be rendered
// from a list — a ref would auto-unwrap to its value inside a template loop.
const selected = reactive<Record<string, string | null>>({
  kind: null,
  os: null,
  clientType: null,
  fingerprint: null,
});
const start = ref(new Date(Date.now() - 24 * 60 * 60_000).toISOString());
const end: Ref<string | null> = ref(null);
const stats: Ref<FrontendErrorStats | null> = ref(null);
const entries: Ref<FrontendErrorEntries | null> = ref(null);
const loading = ref(true);
const loadingMore = ref(false);
const error: Ref<string | null> = ref(null);

const sortColumn = ref('epoch_sec');
const sortDir = ref<'asc' | 'desc'>('desc');

const volumeSeries = [{ label: 'Errors', stroke: '#f87171' }];

const rangeLabel = computed(() => {
  if (!end.value) return null;
  const fmt = (iso: string) => {
    const d = new Date(iso);
    const mon = d.toLocaleString('en-US', { month: 'short' });
    return `${mon} ${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(
      d.getMinutes(),
    ).padStart(2, '0')}`;
  };
  return `${fmt(start.value)} – ${fmt(end.value)}`;
});

const effectiveSpanMinutes = computed(() => {
  if (end.value) {
    return (
      (new Date(end.value).getTime() - new Date(start.value).getTime()) / 60000
    );
  }
  return selectedMinutes.value;
});

const summaryTiles = computed(() => {
  const labels = ['Total Errors', 'Distinct Errors', 'Affected Sessions'];
  const row = stats.value?.summary.rows[0];
  return labels.map((label, i) => ({
    label,
    value: row ? (row[i]?.toLocaleString() ?? '0') : '-',
  }));
});

// The site may simply not be instrumented yet — that reads identically to a
// healthy site, so say which one it is.
const hasData = computed(
  () =>
    (stats.value?.summary.rows[0]?.[0] ?? 0) > 0 || entries.value?.rows.length,
);

// A filter value can be selected and then vanish from the distribution (e.g. it
// only occurs outside the new window); keep it visible with a zero count so it
// can be deselected.
function filterButtons(
  distribution: { rows: any[][] } | undefined,
  key: string,
) {
  if (!distribution) return [];
  const rows = distribution.rows;
  const value = selected[key];
  if (value != null && !rows.some((r) => r[0] === value)) {
    return [...rows, [value, 0]];
  }
  return rows;
}

const filterGroups = computed(() => [
  {
    key: 'kind',
    title: 'Kind',
    rows: filterButtons(stats.value?.kind_distribution, 'kind'),
  },
  {
    key: 'os',
    title: 'OS',
    rows: filterButtons(stats.value?.os_distribution, 'os'),
  },
  {
    key: 'clientType',
    title: 'Client Type',
    rows: filterButtons(stats.value?.client_type_distribution, 'clientType'),
  },
]);

function toggle(key: string, value: string) {
  selected[key] = selected[key] === value ? null : value;
}

function filters(): FrontendErrorFilters {
  return {
    end: end.value ?? undefined,
    kind: selected.kind ?? undefined,
    os: selected.os ?? undefined,
    clientType: selected.clientType ?? undefined,
    fingerprint: selected.fingerprint ?? undefined,
  };
}

async function fetchAll() {
  const f = filters();
  const [statsData, entriesData] = await Promise.all([
    fetchFrontendErrorStats(projectId, siteKey, start.value, f),
    fetchFrontendErrors(projectId, siteKey, start.value, {
      ...f,
      orderBy: sortColumn.value,
      orderDir: sortDir.value,
    }),
  ]);
  stats.value = statsData;
  entries.value = entriesData;
}

async function reload(showSpinner = false) {
  if (showSpinner) loading.value = true;
  error.value = null;
  try {
    await fetchAll();
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}

function selectPeriod(minutes: number) {
  selectedMinutes.value = minutes;
  start.value = new Date(Date.now() - minutes * 60_000).toISOString();
  end.value = null;
  reload(true);
}

function onRangeSelect(rangeStart: string, rangeEnd: string) {
  start.value = rangeStart;
  end.value = rangeEnd;
  reload(true);
}

function clearRange() {
  start.value = new Date(
    Date.now() - selectedMinutes.value * 60_000,
  ).toISOString();
  end.value = null;
  reload(true);
}

function onSort(column: string, dir: 'asc' | 'desc') {
  sortColumn.value = column;
  sortDir.value = dir;
  reload();
}

function onSelectFingerprint(fingerprint: string) {
  toggle('fingerprint', fingerprint);
}

async function loadMore() {
  const next = entries.value?.next;
  if (!next || loadingMore.value) return;
  loadingMore.value = true;
  try {
    const page = await fetchFrontendErrorPage(next);
    entries.value = { ...page, rows: [...entries.value!.rows, ...page.rows] };
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loadingMore.value = false;
  }
}

watch(selected, () => reload());
onMounted(() => reload(true));
</script>

<template>
  <div>
    <SiteTabs
      :project-id="projectId"
      :site-key="siteKey"
      active="frontend-errors"
    />

    <PeriodSelector
      class="mt-4"
      :selected-minutes="selectedMinutes"
      :range-label="rangeLabel"
      @select-period="selectPeriod"
      @range-select="onRangeSelect"
      @clear-range="clearRange"
    />

    <div
      v-if="error"
      class="mt-4 px-4 py-2 bg-red-900/50 border border-red-700 rounded text-sm text-red-300"
    >
      {{ error }}
    </div>

    <div v-if="loading" class="text-center text-gray-500 py-20">Loading...</div>

    <template v-else-if="stats">
      <div class="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div
          v-for="tile in summaryTiles"
          :key="tile.label"
          class="bg-gray-900 border border-gray-800 rounded-lg p-3"
        >
          <div class="text-xs text-gray-500">{{ tile.label }}</div>
          <div class="mt-1 text-lg font-semibold">{{ tile.value }}</div>
        </div>
      </div>

      <div
        v-if="!hasData"
        class="mt-6 px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-sm text-gray-400"
      >
        No browser errors in this window. If this site has never reported any,
        it may not have the reporter installed yet — see
        <span class="font-mono text-gray-300"
          >docs/frontend-error-writing.md</span
        >.
      </div>

      <template v-else>
        <VolumeChart
          v-if="stats.volume?.rows?.length"
          class="mt-6"
          title="Error Volume"
          :rows="stats.volume.rows"
          :series="volumeSeries"
          :span-minutes="effectiveSpanMinutes"
          @select="onRangeSelect"
        />

        <TopErrorsPanel
          v-if="stats.top_errors?.rows?.length"
          class="mt-6"
          :top-errors="stats.top_errors"
          :selected-fingerprint="selected.fingerprint"
          @select="onSelectFingerprint"
        />

        <template v-for="group in filterGroups" :key="group.key">
          <div v-if="group.rows.length" class="mt-6">
            <h3 class="text-sm font-semibold text-gray-400 mb-2">
              {{ group.title }}
            </h3>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="row in group.rows"
                :key="row[0]"
                class="rounded px-3 py-1.5 text-sm border transition-colors cursor-pointer"
                :class="
                  selected[group.key] === row[0]
                    ? 'bg-gray-700 border-gray-500'
                    : 'bg-gray-900 border-gray-800 hover:border-gray-600'
                "
                @click="toggle(group.key, row[0])"
              >
                <span class="font-mono font-medium">{{ row[0] }}</span>
                <span class="text-gray-400 ml-2">
                  {{ row[1]?.toLocaleString() }}
                </span>
              </button>
            </div>
          </div>
        </template>

        <FrontendErrorTable
          v-if="entries && entries.rows.length"
          class="mt-6"
          :entries="entries"
          :sort-column="sortColumn"
          :sort-dir="sortDir"
          :has-more="entries.next !== null"
          :loading-more="loadingMore"
          @sort="onSort"
          @load-more="loadMore"
        />
      </template>
    </template>
  </div>
</template>
