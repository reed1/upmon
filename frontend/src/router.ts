import { createRouter, createWebHistory } from 'vue-router';
import HomeView from './views/HomeView.vue';
import SiteDashboardView from './views/SiteDashboardView.vue';

const router = createRouter({
  history: createWebHistory('/frontend/'),
  routes: [
    { path: '/', component: HomeView },
    { path: '/sites/:projectId/:siteKey', component: SiteDashboardView },
  ],
});

export default router;
