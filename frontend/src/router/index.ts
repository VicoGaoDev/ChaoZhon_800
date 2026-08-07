import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      component: () => import("@/components/layout/AppLayout.vue"),
      children: [
        {
          path: "",
          name: "Home",
          component: () => import("@/views/HomeView.vue"),
        },
        {
          path: "templates",
          name: "Templates",
          component: () => import("@/views/TemplatesView.vue"),
        },
        {
          path: "generate",
          name: "Generate",
          component: () => import("@/views/GenerateView.vue"),
        },
        {
          path: "batch-generate",
          name: "BatchGenerate",
          component: () => import("@/views/BatchGenerateView.vue"),
        },
        {
          path: "history",
          name: "History",
          component: () => import("@/views/HistoryView.vue"),
        },
        {
          path: "profile",
          name: "Profile",
          meta: { requiresAuth: true },
          component: () => import("@/views/ProfileView.vue"),
        },
        {
          path: "credit-logs",
          name: "CreditLogs",
          meta: { requiresAuth: true },
          component: () => import("@/views/CreditLogsView.vue"),
        },
        {
          path: "promo-codes",
          name: "PromoCodes",
          meta: { requiresAuth: true },
          component: () => import("@/views/PromoCodesView.vue"),
        },
        {
          path: "invite-rewards",
          name: "InviteRewards",
          meta: { requiresAuth: true },
          component: () => import("@/views/InviteRewardsView.vue"),
        },
        {
          path: "payment-result",
          name: "PaymentResult",
          meta: { requiresAuth: true },
          component: () => import("@/views/PaymentResultView.vue"),
        },
        {
          path: "api-keys",
          name: "ApiKeys",
          meta: { requiresAuth: true },
          component: () => import("@/views/ApiKeysView.vue"),
        },
        {
          path: "feedbacks",
          name: "FeedbackList",
          meta: { requiresAuth: true },
          component: () => import("@/views/FeedbackListView.vue"),
        },
        {
          path: "feedbacks/:feedbackId",
          name: "FeedbackDetail",
          meta: { requiresAuth: true },
          component: () => import("@/views/FeedbackDetailView.vue"),
        },
        {
          path: "system-messages",
          name: "SystemMessageList",
          meta: { requiresAuth: true },
          component: () => import("@/views/SystemMessageListView.vue"),
        },
        {
          path: "system-messages/:messageId",
          name: "SystemMessageDetail",
          meta: { requiresAuth: true },
          component: () => import("@/views/SystemMessageDetailView.vue"),
        },
        {
          path: "user-agreement",
          name: "UserAgreement",
          meta: { hideTopMenu: true },
          component: () => import("@/views/LegalDocumentView.vue"),
        },
        {
          path: "privacy-policy",
          name: "PrivacyPolicy",
          meta: { hideTopMenu: true },
          component: () => import("@/views/LegalDocumentView.vue"),
        },
        {
          path: "settings",
          name: "Settings",
          meta: { requiresAuth: true },
          component: () => import("@/views/admin/ApiKeyView.vue"),
        },
        {
          path: "admin/templates",
          name: "TemplateManage",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/TemplateManageView.vue"),
        },
        {
          path: "admin/prompt-optimize",
          name: "AdminPromptOptimizeManage",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/PromptOptimizeManageView.vue"),
        },
        {
          path: "admin/users",
          name: "UserManage",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/UserManageView.vue"),
        },
        {
          path: "admin/redeem-keys",
          name: "RedeemKeyManage",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/RedeemKeyManageView.vue"),
        },
        {
          path: "admin/revenue",
          name: "AdminRevenue",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/RevenueView.vue"),
        },
        {
          path: "admin/invite-rewards",
          name: "AdminInviteRewards",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/InviteRewardStatsView.vue"),
        },
        {
          path: "admin/promo-stats",
          name: "AdminPromoStats",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/PromoStatsView.vue"),
        },
        {
          path: "admin/payment-orders",
          name: "AdminPaymentOrders",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/PaymentOrderManageView.vue"),
        },
        {
          path: "admin/user-tasks",
          name: "AdminUserTasks",
          meta: { requiresAdmin: true },
          component: () => import("@/views/HistoryView.vue"),
          props: { adminUserTasks: true },
        },
        {
          path: "admin/dashboard",
          name: "Dashboard",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/DashboardView.vue"),
        },
        {
          path: "admin/error-analytics",
          name: "AdminErrorAnalytics",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/ErrorAnalyticsView.vue"),
        },
        {
          path: "admin/general-settings",
          name: "AdminGeneralSettings",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/GeneralSettingsView.vue"),
        },
        {
          path: "admin/feedbacks",
          name: "AdminFeedbackManage",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/FeedbackManageView.vue"),
        },
        {
          path: "admin/feedbacks/:feedbackId",
          name: "AdminFeedbackDetail",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/FeedbackDetailView.vue"),
        },
        {
          path: "admin/system-messages",
          name: "AdminSystemMessageManage",
          meta: { requiresAdmin: true },
          component: () => import("@/views/admin/SystemMessageManageView.vue"),
        },
        {
          path: "admin/api-key",
          redirect: "/admin/general-settings",
        },
        {
          path: "admin/cos-config",
          name: "CosConfigManage",
          meta: { requiresSuperAdmin: true },
          component: () => import("@/views/admin/CosConfigView.vue"),
        },
        {
          path: "admin/external-api-configs",
          name: "ExternalApiConfigManage",
          meta: { requiresSuperAdmin: true },
          component: () => import("@/views/admin/ExternalApiConfigView.vue"),
        },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: "Home" };
  }
  if (to.meta.requiresSuperAdmin && !auth.isSuperAdmin) {
    return { name: "Templates" };
  }
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: "Templates" };
  }
});

export default router;
