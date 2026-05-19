import { createRouter, createWebHistory } from 'vue-router'

// 路由配置
const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: '首页' }
  },
  {
    path: '/smart-cut',
    name: 'SmartCut',
    component: () => import('@/views/SmartCutView.vue'),
    meta: { title: '智能裁剪' }
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@/views/TaskListView.vue'),
    meta: { title: '任务列表' }
  },
  {
    path: '/tasks/create',
    name: 'TaskCreate',
    component: () => import('@/views/TaskCreateView.vue'),
    meta: { title: '创建任务' }
  },
  {
    path: '/tasks/:id',
    name: 'TaskDetail',
    component: () => import('@/views/TaskDetailView.vue'),
    meta: { title: '任务详情' }
  },
  {
    path: '/materials',
    name: 'Materials',
    component: () => import('@/views/MaterialListView.vue'),
    meta: { title: '素材库' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '系统设置' }
  },
  {
    path: '/settings/config',
    name: 'Config',
    component: () => import('@/views/ConfigView.vue'),
    meta: { title: '参数配置' }
  },
  {
    path: '/settings/system',
    name: 'SystemStatus',
    component: () => import('@/views/SystemStatusView.vue'),
    meta: { title: '系统状态' }
  },
  // 404 页面
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

// 路由守卫 - 仅设置页面标题
router.beforeEach((to) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - AUTOavantar`
  } else {
    document.title = 'AUTOavantar - 数字人视频生成系统'
  }
})

export default router
