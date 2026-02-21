<template>
  <div class="min-h-screen bg-gray-950 text-gray-100">
    <header
      class="flex items-center justify-between px-6 py-4 border-b border-gray-800"
    >
      <router-link to="/" class="text-xl font-bold hover:text-white transition-colors">
        upmon
      </router-link>
    </header>

    <main class="max-w-3xl mx-auto px-4 py-6">
      <router-view />
    </main>
  </div>
</template>
