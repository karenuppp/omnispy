import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'task-list', component: () => import('./views/TaskList.vue') },
    { path: '/tasks/new', name: 'task-new', component: () => import('./views/TaskForm.vue') },
    { path: '/tasks/:id/edit', name: 'task-edit', component: () => import('./views/TaskForm.vue') },
    { path: '/tasks/:id', name: 'task-detail', component: () => import('./views/TaskDetail.vue') },
    { path: '/search', name: 'manual-search', component: () => import('./views/ManualSearch.vue') },
  ],
})

export default router
