<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, shallowRef } from 'vue';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

const props = defineProps<{
  opts: Omit<uPlot.Options, 'width'>;
  data: uPlot.AlignedData;
}>();

const container = ref<HTMLDivElement>();
const chart = shallowRef<uPlot>();

function create() {
  if (!container.value) return;
  chart.value?.destroy();
  chart.value = new uPlot(
    { ...props.opts, width: container.value.clientWidth },
    props.data,
    container.value,
  );
}

const ro = new ResizeObserver((entries) => {
  const width = entries[0].contentRect.width;
  if (chart.value)
    chart.value.setSize({ width, height: props.opts.height ?? 300 });
});

onMounted(() => {
  create();
  if (container.value) ro.observe(container.value);
});

onBeforeUnmount(() => {
  ro.disconnect();
  chart.value?.destroy();
});

watch(
  () => props.data,
  () => {
    if (chart.value) chart.value.setData(props.data);
    else create();
  },
);

watch(() => props.opts, create);
</script>

<template>
  <div ref="container"></div>
</template>
