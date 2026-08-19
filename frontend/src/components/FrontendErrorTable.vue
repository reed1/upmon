<script setup lang="ts">
import { ref } from 'vue';
import type { FrontendErrorEntries } from '../types';
import JsonView from './JsonView.vue';

const props = defineProps<{
  entries: FrontendErrorEntries;
  sortColumn: string;
  sortDir: 'asc' | 'desc';
  hasMore: boolean;
  loadingMore: boolean;
}>();

const emit = defineEmits<{
  sort: [column: string, dir: 'asc' | 'desc'];
  loadMore: [];
}>();

const expandedRow = ref<number | null>(null);

function cell(row: any[], columns: string[], name: string): any {
  const idx = columns.indexOf(name);
  return idx >= 0 ? row[idx] : null;
}

function formatTimestamp(epochSec: number | null): string {
  if (epochSec == null) return '-';
  const d = new Date(epochSec * 1000);
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

const kindColors: Record<string, string> = {
  error: 'text-red-400',
  unhandledrejection: 'text-orange-400',
  manual: 'text-yellow-400',
};

function kindColor(kind: string): string {
  return kindColors[kind] ?? 'text-gray-400';
}

function toggleSort(column: string) {
  if (props.sortColumn === column) {
    emit('sort', column, props.sortDir === 'desc' ? 'asc' : 'desc');
  } else {
    emit('sort', column, 'desc');
  }
}

function toggleRow(i: number) {
  expandedRow.value = expandedRow.value === i ? null : i;
}

function rowToObject(row: any[], columns: string[]): Record<string, unknown> {
  const obj: Record<string, unknown> = {};
  for (let i = 0; i < columns.length; i++) obj[columns[i]] = row[i];
  return obj;
}
</script>

<template>
  <div>
    <h3 class="text-sm font-semibold text-gray-400 mb-2">Error Occurrences</h3>
    <div class="overflow-x-auto">
      <table class="w-full text-sm border-collapse">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-800">
            <th class="py-2 w-6"></th>
            <th
              v-for="col in [
                { key: 'epoch_sec', label: 'Timestamp' },
                { key: 'kind', label: 'Kind' },
                { key: 'error_class', label: 'Error' },
                { key: 'page_url', label: 'Page' },
              ]"
              :key="col.key"
              class="py-2 pr-4 cursor-pointer select-none hover:text-gray-300 transition-colors"
              @click="toggleSort(col.key)"
            >
              {{ col.label }}
              <span v-if="sortColumn === col.key" class="ml-0.5">
                {{ sortDir === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
            <th class="py-2 pr-4">Message</th>
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
                {{ formatTimestamp(cell(row, entries.columns, 'epoch_sec')) }}
              </td>
              <td class="py-1.5 pr-4 font-mono text-xs">
                <span :class="kindColor(cell(row, entries.columns, 'kind'))">
                  {{ cell(row, entries.columns, 'kind') }}
                </span>
              </td>
              <td class="py-1.5 pr-4 font-mono">
                {{ cell(row, entries.columns, 'error_class') ?? '-' }}
              </td>
              <td class="py-1.5 pr-4 text-gray-500 max-w-xs truncate">
                {{ cell(row, entries.columns, 'page_url') }}
              </td>
              <td class="py-1.5 pr-4 text-gray-300 max-w-md truncate">
                {{ cell(row, entries.columns, 'message') }}
              </td>
            </tr>
            <tr v-if="expandedRow === i">
              <td
                colspan="6"
                class="px-4 py-3 bg-gray-950 border-b border-gray-800"
              >
                <pre
                  v-if="cell(row, entries.columns, 'stack')"
                  class="mb-3 overflow-x-auto text-xs text-gray-400 whitespace-pre-wrap"
                  >{{ cell(row, entries.columns, 'stack') }}</pre
                >
                <JsonView :data="rowToObject(row, entries.columns)" />
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-if="hasMore" class="mt-3 flex justify-center">
      <button
        class="px-3 py-1.5 text-xs rounded-md border transition-colors bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-600 hover:text-gray-200 disabled:opacity-50 disabled:cursor-default cursor-pointer"
        :disabled="loadingMore"
        @click="emit('loadMore')"
      >
        {{ loadingMore ? 'Loading…' : 'Load more' }}
      </button>
    </div>
  </div>
</template>
