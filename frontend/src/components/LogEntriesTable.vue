<script setup lang="ts">
import { ref } from 'vue';
import type { AccessLogEntries } from '../types';
import JsonView from './JsonView.vue';

const props = defineProps<{
  entries: AccessLogEntries;
  sortColumn: string;
  sortDir: 'asc' | 'desc';
}>();

const emit = defineEmits<{
  sort: [column: string, dir: 'asc' | 'desc'];
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

function formatDuration(ms: number | null): string {
  if (ms == null) return '-';
  return `${Math.round(ms)}ms`;
}

function statusColor(code: number): string {
  if (code < 300) return 'text-emerald-400';
  if (code < 400) return 'text-yellow-400';
  return 'text-red-400';
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
    <h3 class="text-sm font-semibold text-gray-400 mb-2">Log Entries</h3>
    <div class="overflow-x-auto">
      <table class="w-full text-sm border-collapse">
        <thead>
          <tr class="text-left text-gray-500 border-b border-gray-800">
            <th class="py-2 w-6"></th>
            <th
              v-for="col in [
                { key: 'epoch_sec', label: 'Timestamp', align: '' },
                { key: 'method', label: 'Method', align: '' },
                { key: 'path', label: 'Path', align: '' },
                { key: 'status_code', label: 'Status', align: '' },
                {
                  key: 'duration_ms',
                  label: 'Duration',
                  align: 'text-right',
                },
              ]"
              :key="col.key"
              class="py-2 pr-4 cursor-pointer select-none hover:text-gray-300 transition-colors"
              :class="col.align"
              @click="toggleSort(col.key)"
            >
              {{ col.label }}
              <span v-if="sortColumn === col.key" class="ml-0.5">
                {{ sortDir === 'asc' ? '\u25B2' : '\u25BC' }}
              </span>
            </th>
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
                  formatTimestamp(cell(row, entries.columns, 'epoch_sec'))
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
