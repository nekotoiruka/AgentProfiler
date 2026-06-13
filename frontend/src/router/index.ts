import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/survey',
    },
    {
      path: '/survey',
      name: 'survey',
      component: () => import('@/views/SurveyView.vue'),
    },
    {
      path: '/results',
      name: 'results',
      component: () => import('@/views/ResultsDashboardView.vue'),
    },
    {
      path: '/evolution',
      name: 'evolution',
      component: () => import('@/views/EvolutionView.vue'),
    },
  ],
});

export default router;
