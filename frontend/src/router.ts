import { createRouter, createWebHistory } from 'vue-router';
import HomeView from './views/HomeView.vue';
import SiteDashboardView from './views/SiteDashboardView.vue';
import FrontendErrorsView from './views/FrontendErrorsView.vue';

const router = createRouter({
  history: createWebHistory('/frontend/'),
  routes: [
    { path: '/', component: HomeView },
    { path: '/sites/:projectId/:siteKey', component: SiteDashboardView },
    {
      path: '/sites/:projectId/:siteKey/frontend-errors',
      component: FrontendErrorsView,
    },
  ],
});

export default router;
