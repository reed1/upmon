<script setup lang="ts">
import { useRouter } from 'vue-router';

const props = defineProps<{
  projectId: string;
  siteKey: string;
  active: 'access-logs' | 'frontend-errors';
}>();

const router = useRouter();

const tabs = [
  { key: 'access-logs', label: 'access logs', suffix: '' },
  {
    key: 'frontend-errors',
    label: 'frontend errors',
    suffix: '/frontend-errors',
  },
] as const;

function go(suffix: string) {
  router.push(
    `/sites/${encodeURIComponent(props.projectId)}/${encodeURIComponent(props.siteKey)}${suffix}`,
  );
}
</script>

<template>
  <div>
    <button
      class="text-sm text-gray-400 hover:text-gray-200 transition-colors cursor-pointer"
      @click="router.back()"
    >
      &larr; Back
    </button>

    <h2 class="mt-4 text-lg font-bold">{{ projectId }} / {{ siteKey }}</h2>

    <div class="mt-3 flex gap-4 border-b border-gray-800">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="pb-2 text-sm transition-colors cursor-pointer border-b-2 -mb-px"
        :class="
          active === tab.key
            ? 'border-gray-400 text-gray-100'
            : 'border-transparent text-gray-500 hover:text-gray-300'
        "
        @click="go(tab.suffix)"
      >
        {{ tab.label }}
      </button>
    </div>
  </div>
</template>
