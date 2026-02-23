<script setup lang="ts">
defineProps<{ data: unknown }>();

function classify(value: unknown): string {
  if (value === null) return 'json-null';
  if (typeof value === 'number') return 'json-number';
  if (typeof value === 'boolean') return 'json-boolean';
  return 'json-string';
}

function format(value: unknown): string {
  if (value === null) return 'null';
  if (typeof value === 'string') return `"${value}"`;
  return String(value);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isArray(value: unknown): value is unknown[] {
  return Array.isArray(value);
}
</script>

<template>
  <template v-if="isObject(data)">
    <span class="json-bracket">{</span>
    <div
      v-for="(key, idx) in Object.keys(data)"
      :key="key"
      class="pl-4 break-all"
    >
      <span class="json-key">"{{ key }}"</span>
      <span class="json-punctuation">: </span>
      <template v-if="isObject(data[key]) || isArray(data[key])">
        <JsonView :data="data[key]" />
      </template>
      <span v-else :class="classify(data[key])">{{ format(data[key]) }}</span>
      <span v-if="idx < Object.keys(data).length - 1" class="json-punctuation"
        >,</span
      >
    </div>
    <span class="json-bracket">}</span>
  </template>

  <template v-else-if="isArray(data)">
    <span class="json-bracket">[</span>
    <div v-for="(item, idx) in data" :key="idx" class="pl-4 break-all">
      <template v-if="isObject(item) || isArray(item)">
        <JsonView :data="item" />
      </template>
      <span v-else :class="classify(item)">{{ format(item) }}</span>
      <span v-if="idx < data.length - 1" class="json-punctuation">,</span>
    </div>
    <span class="json-bracket">]</span>
  </template>

  <span v-else :class="classify(data)">{{ format(data) }}</span>
</template>

<style scoped>
.json-bracket {
  color: oklch(0.6 0 0);
}
.json-punctuation {
  color: oklch(0.55 0 0);
}
.json-key {
  color: oklch(0.75 0.15 250);
}
.json-string {
  color: oklch(0.75 0.15 155);
}
.json-number {
  color: oklch(0.78 0.15 75);
}
.json-boolean {
  color: oklch(0.75 0.12 310);
}
.json-null {
  color: oklch(0.55 0 0);
  font-style: italic;
}
</style>
