<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { Ref } from 'vue';
import { fetchStatus, fetchDailySummary } from '../api';
import type { SiteStatus, DailySummaryResponse } from '../types';
import ProjectGroup from '../components/ProjectGroup.vue';

interface SiteView extends SiteStatus {
  has_agent_error: boolean;
}

const sites: Ref<SiteView[]> = ref([]);
const dailySummary: Ref<DailySummaryResponse> = ref({});
const loading = ref(true);
const error: Ref<string | null> = ref(null);
const statusFilter: Ref<'up' | 'down' | 'error' | null> = ref(null);

let intervalId: ReturnType<typeof setInterval> | null = null;

function buildSiteViews(
  statuses: SiteStatus[],
  summary: DailySummaryResponse,
): SiteView[] {
  return statuses.map((s) => {
    const entry = summary[s.project_id]?.[s.site_key];
    return {
      ...s,
      has_agent_error:
        !!entry?.has_agent &&
        (entry.cleanup_ok === false || entry.errors_ok === false),
    };
  });
}

const upCount = computed(() => sites.value.filter((s) => s.is_up).length);
const downCount = computed(() => sites.value.filter((s) => !s.is_up).length);
const errorCount = computed(
  () => sites.value.filter((s) => s.has_agent_error).length,
);

const filtered = computed(() => {
  if (statusFilter.value === 'up') return sites.value.filter((s) => s.is_up);
  if (statusFilter.value === 'down') return sites.value.filter((s) => !s.is_up);
  if (statusFilter.value === 'error')
    return sites.value.filter((s) => s.has_agent_error);
  return sites.value;
});

const projectIds = computed(() => {
  const ids = new Set(filtered.value.map((s) => s.project_id));
  return [...ids].sort();
});

function sitesForProject(projectId: string): SiteView[] {
  return filtered.value.filter((s) => s.project_id === projectId);
}

function toggleFilter(filter: 'up' | 'down' | 'error') {
  statusFilter.value = statusFilter.value === filter ? null : filter;
}

async function refresh() {
  try {
    const [statusData, summaryData] = await Promise.all([
      fetchStatus(),
      fetchDailySummary(),
    ]);
    dailySummary.value = summaryData;
    sites.value = buildSiteViews(statusData, summaryData);
    error.value = null;
  } catch (e) {
    error.value = (e as Error).message;
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  refresh();
  intervalId = setInterval(refresh, 60_000);
});

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId);
});
</script>

<template>
  <div
    v-if="error"
    class="mb-4 px-4 py-2 bg-red-900/50 border border-red-700 rounded text-sm text-red-300"
  >
    {{ error }}
  </div>

  <div v-if="loading" class="text-center text-gray-500 py-20">Loading...</div>

  <div v-else class="space-y-8">
    <div class="flex flex-wrap gap-2 text-sm">
      <button
        class="flex items-center gap-2 rounded px-3 py-1.5 border transition-colors cursor-pointer"
        :class="
          statusFilter === 'up'
            ? 'bg-gray-700 border-gray-500'
            : 'bg-gray-900 border-gray-800 hover:border-gray-600'
        "
        @click="toggleFilter('up')"
      >
        <span class="size-2.5 rounded-full bg-emerald-500" />
        <span class="text-emerald-400 font-medium">{{ upCount }} up</span>
      </button>
      <button
        v-if="downCount > 0"
        class="flex items-center gap-2 rounded px-3 py-1.5 border transition-colors cursor-pointer"
        :class="
          statusFilter === 'down'
            ? 'bg-gray-700 border-gray-500'
            : 'bg-gray-900 border-gray-800 hover:border-gray-600'
        "
        @click="toggleFilter('down')"
      >
        <span class="size-2.5 rounded-full bg-red-500" />
        <span class="text-red-400 font-medium">{{ downCount }} down</span>
      </button>
      <button
        v-if="errorCount > 0"
        class="flex items-center gap-2 rounded px-3 py-1.5 border transition-colors cursor-pointer"
        :class="
          statusFilter === 'error'
            ? 'bg-gray-700 border-gray-500'
            : 'bg-gray-900 border-gray-800 hover:border-gray-600'
        "
        @click="toggleFilter('error')"
      >
        <span class="size-2.5 rounded-full bg-amber-500" />
        <span class="text-amber-400 font-medium"
          >{{ errorCount }} with errors</span
        >
      </button>
    </div>
    <ProjectGroup
      v-for="pid in projectIds"
      :key="pid"
      :project-id="pid"
      :sites="sitesForProject(pid)"
      :daily-summary="dailySummary[pid] ?? {}"
    />
  </div>
</template>
