<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { fetchStatus, fetchDailySummary } from './api.js'
import ProjectGroup from './components/ProjectGroup.vue'

const statuses = ref([])
const dailySummary = ref({})
const loading = ref(true)
const error = ref(null)
const lastRefreshed = ref(null)

let intervalId = null

const projectIds = computed(() => {
  const ids = new Set(statuses.value.map(s => s.project_id))
  return [...ids].sort()
})

function sitesForProject(projectId) {
  return statuses.value.filter(s => s.project_id === projectId)
}

function formatTime(date) {
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

async function refresh() {
  try {
    const [statusData, summaryData] = await Promise.all([
      fetchStatus(),
      fetchDailySummary(),
    ])
    statuses.value = statusData
    dailySummary.value = summaryData
    lastRefreshed.value = new Date()
    error.value = null
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refresh()
  intervalId = setInterval(refresh, 60_000)
})

onUnmounted(() => {
  clearInterval(intervalId)
})
</script>

<template>
  <div class="min-h-screen bg-gray-950 text-gray-100">
    <header class="flex items-center justify-between px-6 py-4 border-b border-gray-800">
      <h1 class="text-xl font-bold">upmon</h1>
      <span v-if="lastRefreshed" class="text-sm text-gray-500">
        refreshed {{ formatTime(lastRefreshed) }}
      </span>
    </header>

    <main class="max-w-3xl mx-auto px-4 py-6">
      <div v-if="error" class="mb-4 px-4 py-2 bg-red-900/50 border border-red-700 rounded text-sm text-red-300">
        {{ error }}
      </div>

      <div v-if="loading" class="text-center text-gray-500 py-20">Loading...</div>

      <div v-else class="space-y-8">
        <ProjectGroup
          v-for="pid in projectIds"
          :key="pid"
          :project-id="pid"
          :sites="sitesForProject(pid)"
          :daily-summary="dailySummary[pid] ?? {}"
        />
      </div>
    </main>
  </div>
</template>
