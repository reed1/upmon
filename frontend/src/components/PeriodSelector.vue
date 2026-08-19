<script setup lang="ts">
import { ref } from 'vue';
import { VueDatePicker } from '@vuepic/vue-datepicker';
import '@vuepic/vue-datepicker/dist/main.css';

defineProps<{
  selectedMinutes: number;
  rangeLabel: string | null;
}>();

const emit = defineEmits<{
  selectPeriod: [minutes: number];
  rangeSelect: [start: string, end: string];
  clearRange: [];
}>();

const periods = [
  { label: '5m', minutes: 5 },
  { label: '10m', minutes: 10 },
  { label: '30m', minutes: 30 },
  { label: '1h', minutes: 1 * 60 },
  { label: '6h', minutes: 6 * 60 },
  { label: '12h', minutes: 12 * 60 },
  { label: '1d', minutes: 24 * 60 },
  { label: '2d', minutes: 2 * 24 * 60 },
  { label: '7d', minutes: 7 * 24 * 60 },
  { label: '30d', minutes: 30 * 24 * 60 },
] as const;

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
  emit('rangeSelect', startOfDay.toISOString(), dayAfterEnd.toISOString());
}
</script>

<template>
  <div>
    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="p in periods"
        :key="p.minutes"
        class="px-2.5 py-1 text-xs rounded-md border transition-colors"
        :class="
          selectedMinutes === p.minutes
            ? 'bg-gray-700 border-gray-600 text-gray-100'
            : 'bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-600 hover:text-gray-200'
        "
        @click="emit('selectPeriod', p.minutes)"
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
        @click="emit('clearRange')"
      >
        <svg class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
          <path
            d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
          />
        </svg>
      </button>
    </div>
  </div>
</template>
