<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { Ref } from 'vue';
import {
  fetchStatus,
  fetchDailySummary,
  fetchAccessLogSites,
} from '../api';
import type {
  SiteStatus,
  DailySummaryResponse,
  AccessLogSiteInfo,
} from '../types';
import ProjectGroup from '../components/ProjectGroup.vue';

const statuses: Ref<SiteStatus[]> = ref([]);
const dailySummary: Ref<DailySummaryResponse> = ref({});
const accessLogSites: Ref<AccessLogSiteInfo[]> = ref([]);
const loading = ref(true);
const error: Ref<string | null> = ref(null);
const lastRefreshed: Ref<Date | null> = ref(null);

let intervalId: ReturnType<typeof setInterval> | null = null;

const upCount = computed(() => statuses.value.filter((s) => s.is_up).length);
const downCount = computed(() => statuses.value.filter((s) => !s.is_up).length);

const projectIds = computed(() => {
  const ids = new Set(statuses.value.map((s) => s.project_id));
  return [...ids].sort();
});

function sitesForProject(projectId: string): SiteStatus[] {
  return statuses.value.filter((s) => s.project_id === projectId);
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

async function refresh() {
  try {
    const [statusData, summaryData, accessLogData] = await Promise.all([
      fetchStatus(),
      fetchDailySummary(),
      fetchAccessLogSites().catch(() => [] as AccessLogSiteInfo[]),
    ]);
    statuses.value = statusData;
    dailySummary.value = summaryData;
    accessLogSites.value = accessLogData;
    lastRefreshed.value = new Date();
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
    <div class="flex items-center gap-6 text-sm">
      <div class="flex items-center gap-2">
        <span class="size-2.5 rounded-full bg-emerald-500" />
        <span class="text-gray-300">{{ upCount }} up</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="size-2.5 rounded-full bg-red-500" />
        <span class="text-gray-300">{{ downCount }} down</span>
      </div>
    </div>
    <ProjectGroup
      v-for="pid in projectIds"
      :key="pid"
      :project-id="pid"
      :sites="sitesForProject(pid)"
      :daily-summary="dailySummary[pid] ?? {}"
      :access-log-sites="accessLogSites"
    />
  </div>
</template>
