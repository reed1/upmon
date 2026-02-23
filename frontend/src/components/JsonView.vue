<script setup lang="ts">
defineProps<{ data: Record<string, unknown> }>();

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
</script>

<template>
  <div class="font-mono text-xs leading-relaxed">
    <span class="json-bracket">{</span>
    <div
      v-for="(key, idx) in Object.keys(data)"
      :key="key"
      class="pl-4 break-all"
    >
      <span class="json-key">"{{ key }}"</span>
      <span class="json-punctuation">: </span>
      <span :class="classify(data[key])">{{ format(data[key]) }}</span>
      <span v-if="idx < Object.keys(data).length - 1" class="json-punctuation"
        >,</span
      >
    </div>
    <span class="json-bracket">}</span>
  </div>
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
