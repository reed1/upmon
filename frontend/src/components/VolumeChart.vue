<script setup lang="ts">
import { computed } from 'vue';
import uPlot from 'uplot';
import UPlotChart from './UPlotChart.vue';

const props = defineProps<{
  rows: any[][];
  spanMinutes: number;
}>();

const emit = defineEmits<{
  select: [start: string, end: string];
}>();

const data = computed<uPlot.AlignedData>(() => {
  if (!props.rows.length) return [[], [], []];
  const timestamps = props.rows.map(
    (r) => new Date(r[0] + 'Z').getTime() / 1000,
  );
  const ok = props.rows.map((r) => r[1] as number);
  const notOk = props.rows.map((r) => r[2] as number);
  return [timestamps, ok, notOk];
});

function onSelect(u: uPlot) {
  const { left, width } = u.select;
  if (width < 2) return;

  const startEpoch = u.posToVal(left, 'x');
  const endEpoch = u.posToVal(left + width, 'x');

  emit(
    'select',
    new Date(startEpoch * 1000).toISOString(),
    new Date(endEpoch * 1000).toISOString(),
  );

  u.setSelect({ left: 0, top: 0, width: 0, height: 0 }, false);
}

const opts = computed<Omit<uPlot.Options, 'width'>>(() => {
  const span = props.spanMinutes;
  const isMinutes = span < 180;
  const isHours = span < 4320;
  return {
    height: 250,
    legend: { show: true },
    cursor: {
      show: true,
      x: true,
      y: false,
      drag: { x: true, y: false, setScale: false },
    },
    axes: [
      {
        stroke: '#6b7280',
        grid: { stroke: '#1f2937', width: 1 },
        ticks: { stroke: '#374151', width: 1 },
        values: isMinutes
          ? '{HH}:{mm}'
          : isHours
            ? '{MMM} {DD} {HH}:{mm}'
            : '{MMM} {DD}',
      },
      {
        stroke: '#6b7280',
        grid: { stroke: '#1f2937', width: 1 },
        ticks: { stroke: '#374151', width: 1 },
      },
    ],
    series: [
      {},
      {
        label: '2xx',
        stroke: '#34d399',
        width: 2,
        value: (_u: uPlot, v: number | null) =>
          v == null ? '—' : v.toLocaleString(),
      },
      {
        label: 'Errors',
        stroke: '#f87171',
        width: 2,
        value: (_u: uPlot, v: number | null) =>
          v == null ? '—' : v.toLocaleString(),
      },
    ],
    hooks: {
      setSelect: [onSelect],
    },
  };
});
</script>

<template>
  <div v-if="data[0].length">
    <h3 class="text-sm font-semibold text-gray-400 mb-2">Request Volume</h3>
    <div class="bg-gray-900 border border-gray-800 rounded-lg p-3">
      <UPlotChart :opts="opts" :data="data" />
    </div>
  </div>
</template>

<style scoped>
:deep(.u-select) {
  background: rgba(255, 255, 255, 0.07);
}
:deep(.u-legend) {
  font-size: 0.8rem;
  color: #9ca3af;
}
:deep(.u-legend .u-value) {
  font-weight: 600;
}
</style>
