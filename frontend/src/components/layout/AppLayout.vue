<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, h, provide, nextTick, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { message, notification } from "ant-design-vue";
import {
  login as apiLogin,
  register as apiRegister,
  forgotPassword as apiForgotPassword,
  getMe,
  getContactConfig,
  getAnnouncementConfig,
  redeemCreditKey,
  validatePromoCode,
} from "@/api/auth";
import { validateInviteCode } from "@/api/inviteRewards";
import { createPaymentOrder, listPaymentPlans } from "@/api/payments";
import { createFeedback, getMyCompletedUnreadFeedbackCount } from "@/api/feedback";
import { getAdminUnresolvedFeedbackCount } from "@/api/admin";
import { registerCloudbaseAccount, sendPasswordResetEmailCode, sendRegisterEmailCode } from "@/lib/cloudbase";
import { withBaseUrl } from "@/lib/assets";
import {
  getStoredAdminUnresolvedFeedbackCount,
  setStoredAdminUnresolvedFeedbackCount,
  subscribeAdminUnresolvedFeedbackCount,
} from "@/lib/adminFeedbackNotice";
import {
  getStoredUserCompletedUnreadFeedbackCount,
  setStoredUserCompletedUnreadFeedbackCount,
  subscribeUserCompletedUnreadFeedbackCount,
} from "@/lib/userFeedbackNotice";
import { getMyUnreadSystemMessageCount, listMySystemMessages } from "@/api/systemMessages";
import {
  getStoredUnreadSystemMessageCount,
  setStoredUnreadSystemMessageCount,
  subscribeUnreadSystemMessageCount,
} from "@/lib/systemMessageNotice";
import { subscribeAuthSessionExpired } from "@/lib/authSessionNotice";
import { APP_THEME_ATTRIBUTE, type AppThemeName } from "@/config/theme";
import { getCurrentTheme } from "@/lib/theme";
import type { AnnouncementConfig, PaymentPlan } from "@/types";
import {
  PictureOutlined,
  SettingOutlined,
  TeamOutlined,
  BarChartOutlined,
  BugOutlined,
  KeyOutlined,
  CloudUploadOutlined,
  LogoutOutlined,
  LockOutlined,
  UserOutlined,
  UserAddOutlined,
  ThunderboltOutlined,
  MenuOutlined,
  MailOutlined,
  MessageOutlined,
  GiftOutlined,
  AccountBookOutlined,
  CheckOutlined,
  ShareAltOutlined,
} from "@ant-design/icons-vue";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const isAdmin = computed(() => auth.isAdmin);
const isSuperAdmin = computed(() => auth.isSuperAdmin);
const showRegisterPromoCode = true;
const hideTopMenu = computed(() => route.meta.hideTopMenu === true);
const mobileDrawerOpen = ref(false);
const routeTransitionName = ref("route-page-forward");
const canManagePromoCodes = computed(() => auth.user?.is_whitelisted === true);

const routeOrder = new Map<string, number>([
  ["/", 0],
  ["/templates", 1],
  ["/generate", 2],
  ["/history", 3],
  ["/profile", 4],
  ["/api-keys", 5],
  ["/system-messages", 6],
  ["/system-messages/:messageId", 7],
  ["/settings", 8],
  ["/credit-logs", 9],
  ["/promo-codes", 10],
  ["/invite-rewards", 11],
  ["/feedbacks", 12],
  ["/feedbacks/:feedbackId", 13],
  ["/admin/templates", 14],
  ["/admin/users", 15],
  ["/admin/user-tasks", 16],
  ["/admin/dashboard", 17],
  ["/admin/error-analytics", 18],
  ["/admin/general-settings", 19],
  ["/admin/redeem-keys", 20],
  ["/admin/revenue", 21],
  ["/admin/invite-rewards", 22],
  ["/admin/promo-stats", 23],
  ["/admin/payment-orders", 24],
  ["/admin/feedbacks", 25],
  ["/admin/feedbacks/:feedbackId", 26],
  ["/admin/system-messages", 27],
  ["/admin/cos-config", 28],
  ["/admin/external-api-configs", 29],
]);

const currentTheme = ref<AppThemeName>(getCurrentTheme());
let themeObserver: MutationObserver | null = null;
const adminUnresolvedFeedbackCount = ref(getStoredAdminUnresolvedFeedbackCount());
let unsubscribeAdminFeedbackCount: (() => void) | null = null;
const userCompletedUnreadFeedbackCount = ref(getStoredUserCompletedUnreadFeedbackCount());
let unsubscribeUserFeedbackCount: (() => void) | null = null;
const userUnreadSystemMessageCount = ref(getStoredUnreadSystemMessageCount());
let unsubscribeSystemMessageCount: (() => void) | null = null;
let systemMessagePollTimer: number | null = null;
let unsubscribeAuthSessionExpired: (() => void) | null = null;
const UNRESOLVED_FEEDBACK_NOTIFICATION_KEY = "global-admin-unresolved-feedback";
const USER_UNREAD_SYSTEM_MESSAGE_NOTIFICATION_KEY = "global-user-unread-system-message";
const INVITE_CODE_SESSION_KEY = "800ai.personalInviteCode";
const notifiedUnreadSystemMessageIdsByUser = new Map<string, Set<string>>();

const primaryMenuItems = [
  { key: "templates", label: "创意模版", iconSrc: withBaseUrl("nav-templates.svg"), darkIconSrc: withBaseUrl("nav-templates-mono.svg") },
  { key: "generate", label: "AI 生图", iconSrc: withBaseUrl("nav-generate.svg") },
  { key: "history", label: "历史图片", iconSrc: withBaseUrl("nav-history.svg"), darkIconSrc: withBaseUrl("nav-history-mono.svg") },
];

function getPrimaryMenuIconSrc(item: (typeof primaryMenuItems)[number]) {
  if (currentTheme.value !== "warm" && item.darkIconSrc) {
    return item.darkIconSrc;
  }
  return item.iconSrc;
}

const adminMenuItems = computed(() =>
  [
    { key: "/admin/templates", label: "模版管理", icon: PictureOutlined, superAdminOnly: false },
    { key: "/admin/users", label: "用户管理", icon: TeamOutlined, superAdminOnly: false },
    { key: "/admin/user-tasks", label: "用户任务", icon: PictureOutlined, superAdminOnly: false },
    { key: "/admin/dashboard", label: "数据统计", icon: BarChartOutlined, superAdminOnly: false },
    { key: "/admin/error-analytics", label: "错误统计", icon: BugOutlined, superAdminOnly: false },
    { key: "/admin/general-settings", label: "通用设置", icon: SettingOutlined, superAdminOnly: false },
    { key: "/admin/redeem-keys", label: "兑换码", icon: GiftOutlined, superAdminOnly: false },
    { key: "/admin/payment-orders", label: "购买订单", icon: AccountBookOutlined, superAdminOnly: false },
    { key: "/admin/invite-rewards", label: "邀请奖励", icon: ShareAltOutlined, superAdminOnly: false },
    { key: "/admin/feedbacks", label: "用户反馈", icon: MessageOutlined, superAdminOnly: false },
    { key: "/admin/system-messages", label: "系统邮件", icon: MailOutlined, superAdminOnly: false },
    { key: "/admin/cos-config", label: "COS 配置", icon: CloudUploadOutlined, superAdminOnly: true },
    { key: "/admin/external-api-configs", label: "接口管理", icon: KeyOutlined, superAdminOnly: true },
  ].filter((item) => !item.superAdminOnly || isSuperAdmin.value)
);
const adminMenuBaseItems = computed(() =>
  adminMenuItems.value.filter((item) => [
    "/admin/templates",
    "/admin/users",
    "/admin/user-tasks",
    "/admin/dashboard",
    "/admin/error-analytics",
    "/admin/general-settings",
  ].includes(item.key))
);
const adminMenuBusinessItems = computed(() =>
  adminMenuItems.value.filter((item) => [
    "/admin/redeem-keys",
    "/admin/payment-orders",
    "/admin/invite-rewards",
  ].includes(item.key))
);
const adminMenuNoticeItems = computed(() =>
  adminMenuItems.value.filter((item) => ["/admin/feedbacks", "/admin/system-messages"].includes(item.key))
);
const adminMenuConfigItems = computed(() =>
  adminMenuItems.value.filter((item) => ["/admin/cos-config", "/admin/external-api-configs"].includes(item.key))
);

const hasAdminUnresolvedFeedback = computed(() => adminUnresolvedFeedbackCount.value > 0);
const hasUserUnreadFeedback = computed(() => userCompletedUnreadFeedbackCount.value > 0);
const hasUserUnreadSystemMessage = computed(() => userUnreadSystemMessageCount.value > 0);
const hasUserUnreadNotice = computed(() => hasUserUnreadFeedback.value || hasUserUnreadSystemMessage.value);

const userMenuItems = computed(() => [
  { key: "profile", label: "个人主页", icon: UserOutlined, danger: false },
  { key: "credits", label: "积分明细", icon: ThunderboltOutlined, danger: false },
  { key: "invite-rewards", label: "邀请奖励", icon: ShareAltOutlined, danger: false },
  ...(canManagePromoCodes.value ? [{ key: "promo-codes", label: "我的推广码", icon: GiftOutlined, danger: false }] : []),
  { key: "settings", label: "设置", icon: SettingOutlined, danger: false },
  { key: "my-feedback", label: "我的反馈", icon: MessageOutlined, danger: false },
  { key: "system-messages", label: "系统消息", icon: MailOutlined, danger: false },
  { key: "logout", label: "退出登录", icon: LogoutOutlined, danger: true },
]);
const userMenuAccountItems = computed(() =>
  userMenuItems.value.filter((item) => ["profile", "credits", "invite-rewards", "promo-codes", "settings"].includes(item.key))
);
const userMenuNoticeItems = computed(() =>
  userMenuItems.value.filter((item) => ["my-feedback", "system-messages"].includes(item.key))
);
const userMenuDangerItems = computed(() => userMenuItems.value.filter((item) => item.danger));

const creditPurchasePlans = ref<PaymentPlan[]>([]);

function getRouteRank(path: string) {
  if (path.startsWith("/feedbacks/")) return routeOrder.get("/feedbacks/:feedbackId") ?? 0;
  if (path.startsWith("/system-messages/")) return routeOrder.get("/system-messages/:messageId") ?? 0;
  if (path.startsWith("/admin/feedbacks/")) return routeOrder.get("/admin/feedbacks/:feedbackId") ?? 0;
  return routeOrder.get(path) ?? 0;
}

const selectedKeys = computed(() => {
  const p = route.path;
  if (p.startsWith("/admin")) return ["admin"];
  if (p === "/") return [];
  if (p === "/templates") return ["templates"];
  if (p === "/batch-generate") return ["batch-generate"];
  if (p === "/history") return ["history"];
  if (
    p === "/profile" ||
    p === "/settings" ||
    p === "/credit-logs" ||
    p === "/invite-rewards" ||
    p === "/promo-codes" ||
    p === "/api-keys" ||
    p.startsWith("/feedbacks") ||
    p.startsWith("/system-messages")
  ) return [];
  return ["generate"];
});

const adminSelectedKeys = computed(() => {
  if (!route.path.startsWith("/admin")) return [];
  if (route.path.startsWith("/admin/feedbacks")) return ["/admin/feedbacks"];
  return [route.path];
});

watch(
  () => route.path,
  (to, from) => {
    const toRank = getRouteRank(to);
    const fromRank = getRouteRank(from ?? "");
    routeTransitionName.value = toRank < fromRank ? "route-page-back" : "route-page-forward";
  },
  { immediate: true }
);

watch(
  () => route.path,
  (path) => {
    if (path === "/") {
      void syncAdminUnresolvedFeedbackCount({ showToast: true });
    }
  }
);

function handleMenuClick({ key }: { key: string }) {
  mobileDrawerOpen.value = false;
  if (key === "templates") router.push("/templates");
  else if (key === "generate") router.push("/generate");
  else if (key === "history") {
    if (!auth.isLoggedIn) {
      loginModalVisible.value = true;
      return;
    }
    router.push("/history");
  }
}

function handleAdminMenu({ key }: { key: string }) {
  mobileDrawerOpen.value = false;
  router.push(key);
}

function handleUserMenu({ key }: { key: string }) {
  mobileDrawerOpen.value = false;
  if (key === "profile") router.push("/profile");
  else if (key === "system-messages") router.push("/system-messages");
  else if (key === "my-feedback") router.push("/feedbacks");
  else if (key === "settings") router.push("/settings");
  else if (key === "credits") router.push("/credit-logs");
  else if (key === "invite-rewards") router.push("/invite-rewards");
  else if (key === "promo-codes") router.push("/promo-codes");
  else if (key === "api-keys") router.push("/api-keys");
  else if (key === "logout") {
    resetUserUnreadSystemMessageNotificationState();
    auth.logout();
    setStoredUnreadSystemMessageCount(0);
    stopSystemMessagePolling();
    router.push("/");
  }
}

function openInviteRewardsEntry() {
  mobileDrawerOpen.value = false;
  if (!auth.isLoggedIn) {
    openAuthModal("login");
    return;
  }
  router.push("/invite-rewards");
}

async function syncAdminUnresolvedFeedbackCount(options?: { showToast?: boolean }) {
  if (!auth.isLoggedIn || !auth.isAdmin) return;
  try {
    const { count } = await getAdminUnresolvedFeedbackCount();
    adminUnresolvedFeedbackCount.value = setStoredAdminUnresolvedFeedbackCount(count);
    if (options?.showToast && count > 0) {
      notification.warning({
        key: UNRESOLVED_FEEDBACK_NOTIFICATION_KEY,
        message: "有用户反馈未处理",
        description: `当前有 ${count} 条未完成的用户反馈，点击前往处理。`,
        placement: "topRight",
        duration: 5,
        style: { cursor: "pointer" },
        onClick: () => {
          notification.close(UNRESOLVED_FEEDBACK_NOTIFICATION_KEY);
          router.push("/admin/feedbacks");
        },
      });
      return;
    }
    notification.close(UNRESOLVED_FEEDBACK_NOTIFICATION_KEY);
  } catch {
    // ignore unresolved feedback count failures
  }
}

async function syncUserCompletedUnreadFeedbackCount() {
  if (!auth.isLoggedIn) return;
  try {
    const { count } = await getMyCompletedUnreadFeedbackCount();
    userCompletedUnreadFeedbackCount.value = setStoredUserCompletedUnreadFeedbackCount(count);
  } catch {
    // ignore user unread feedback count failures
  }
}

async function syncUserUnreadSystemMessageCount(options?: { showToast?: boolean; forceToast?: boolean }) {
  if (!auth.isLoggedIn) return;
  try {
    const previous = userUnreadSystemMessageCount.value;
    const { count } = await getMyUnreadSystemMessageCount();
    userUnreadSystemMessageCount.value = setStoredUnreadSystemMessageCount(count);
    if (options?.showToast && count > 0 && (options.forceToast || count > previous)) {
      await notifyLatestUnreadSystemMessage(count);
    }
  } catch {
    // ignore system message count failures
  }
}

async function notifyLatestUnreadSystemMessage(unreadCount: number) {
  if (unreadCount <= 0) {
    notification.close(USER_UNREAD_SYSTEM_MESSAGE_NOTIFICATION_KEY);
    return;
  }

  const { items } = await listMySystemMessages(1, Math.max(5, unreadCount));
  const latestUnread = items.find((item) => !item.is_read);
  const userKey = auth.user?.business_id || auth.user?.id || "anonymous";
  const notifiedIds = notifiedUnreadSystemMessageIdsByUser.get(userKey) || new Set<string>();
  if (!latestUnread || notifiedIds.has(latestUnread.message_id)) return;

  notifiedIds.add(latestUnread.message_id);
  notifiedUnreadSystemMessageIdsByUser.set(userKey, notifiedIds);
  notification.info({
    key: USER_UNREAD_SYSTEM_MESSAGE_NOTIFICATION_KEY,
    message: latestUnread.subject || "新的系统消息",
    description: unreadCount > 1 ? `你有 ${unreadCount} 条未读系统消息，点击查看详情。` : "你有新的系统消息，点击查看详情。",
    placement: "topRight",
    duration: 6,
    style: { cursor: "pointer" },
    onClick: () => {
      notification.close(USER_UNREAD_SYSTEM_MESSAGE_NOTIFICATION_KEY);
      router.push(`/system-messages/${latestUnread.message_id}`);
    },
  });
}

function resetUserUnreadSystemMessageNotificationState() {
  notification.close(USER_UNREAD_SYSTEM_MESSAGE_NOTIFICATION_KEY);
  notifiedUnreadSystemMessageIdsByUser.clear();
}

function startSystemMessagePolling() {
  if (typeof window === "undefined" || systemMessagePollTimer) return;
  systemMessagePollTimer = window.setInterval(() => {
    void syncUserUnreadSystemMessageCount({ showToast: true });
  }, 60000);
}

function stopSystemMessagePolling() {
  if (!systemMessagePollTimer) return;
  window.clearInterval(systemMessagePollTimer);
  systemMessagePollTimer = null;
}

const loginModalVisible = ref(false);
provide("loginModalVisible", loginModalVisible);
const authTab = ref<"login" | "register">("login");
const loginForm = reactive({ account: "", password: "" });
const loginLoading = ref(false);
const forgotPasswordDialogOpen = ref(false);
const forgotPasswordForm = reactive({
  email: "",
  verificationCode: "",
  verificationId: "",
  newPassword: "",
  confirmPassword: "",
});
const forgotPasswordLoading = ref(false);
const forgotPasswordCodeLoading = ref(false);
const registerForm = reactive({
  email: "",
  verificationCode: "",
  username: "",
  password: "",
  confirmPassword: "",
  promoCode: "",
  agreedTerms: false,
});
const registerLoading = ref(false);
const registerCodeLoading = ref(false);
const redeemDialogOpen = ref(false);
const redeemLoading = ref(false);
const redeemForm = reactive({ key: "" });
const purchaseDialogOpen = ref(false);
const selectedPurchasePlanKey = ref("");
const selectedPurchasePlan = computed(() =>
  creditPurchasePlans.value.find((item) => item.key === selectedPurchasePlanKey.value && item.purchasable) || null
);
const purchasePlansLoading = ref(false);
const purchaseLoading = ref(false);
const purchaseFeedbackDialogOpen = ref(false);
const purchaseFeedbackSubmitting = ref(false);
const purchaseFeedbackForm = reactive({ content: "" });
const authExpiredPromptVisible = ref(false);
const expiredSessionRedirectPath = ref("");

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function normalizeInviteCode(code?: string | null) {
  return (code || "").trim().toUpperCase().replace(/\s+/g, "");
}

function isPersonalInviteCodeValue(code?: string | null) {
  return /^U[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{7}$/.test(normalizeInviteCode(code));
}

function getStoredInviteCode() {
  try {
    const code = normalizeInviteCode(sessionStorage.getItem(INVITE_CODE_SESSION_KEY));
    return isPersonalInviteCodeValue(code) ? code : "";
  } catch {
    return "";
  }
}

function clearStoredInviteCode() {
  try {
    sessionStorage.removeItem(INVITE_CODE_SESSION_KEY);
  } catch {
    // ignore storage errors
  }
}

function applyStoredInviteCodeToRegisterForm() {
  const storedCode = getStoredInviteCode();
  if (storedCode && !registerForm.promoCode.trim()) {
    registerForm.promoCode = storedCode;
  }
}

function captureInviteCodeFromRoute() {
  if (auth.isLoggedIn) return;
  const rawInvite = Array.isArray(route.query.invite) ? route.query.invite[0] : route.query.invite;
  const inviteCode = normalizeInviteCode(typeof rawInvite === "string" ? rawInvite : "");
  if (!isPersonalInviteCodeValue(inviteCode)) return;
  try {
    sessionStorage.setItem(INVITE_CODE_SESSION_KEY, inviteCode);
  } catch {
    // ignore storage errors
  }
  if (authTab.value === "register" || loginModalVisible.value) {
    registerForm.promoCode = inviteCode;
  }
}

function openAuthModal(tab: "login" | "register") {
  mobileDrawerOpen.value = false;
  authTab.value = tab;
  loginModalVisible.value = true;
  if (tab === "register") {
    applyStoredInviteCodeToRegisterForm();
  }
}

function openForgotPasswordDialog() {
  forgotPasswordForm.email = loginForm.account.includes("@") ? loginForm.account.trim() : "";
  forgotPasswordDialogOpen.value = true;
  loginModalVisible.value = false;
}

function resetForgotPasswordForm() {
  forgotPasswordForm.email = "";
  forgotPasswordForm.verificationCode = "";
  forgotPasswordForm.verificationId = "";
  forgotPasswordForm.newPassword = "";
  forgotPasswordForm.confirmPassword = "";
}

function handleAuthSessionExpired(detail: { redirectPath: string }) {
  resetUserUnreadSystemMessageNotificationState();
  auth.logout();
  expiredSessionRedirectPath.value = detail.redirectPath || route.fullPath || "/templates";
  if (loginModalVisible.value) return;
  authTab.value = "login";
  loginModalVisible.value = true;
  if (authExpiredPromptVisible.value) return;
  authExpiredPromptVisible.value = true;
  message.warning("登录已过期，请重新登录");
}

watch(loginModalVisible, (open) => {
  if (!open) {
    authExpiredPromptVisible.value = false;
  }
});

watch(
  () => route.query.invite,
  () => {
    captureInviteCodeFromRoute();
  },
  { immediate: true }
);

watch(authTab, (tab) => {
  if (tab === "register") {
    applyStoredInviteCodeToRegisterForm();
  }
});

function resetAuthForms() {
  loginForm.account = "";
  loginForm.password = "";
  registerForm.email = "";
  registerForm.verificationCode = "";
  registerForm.username = "";
  registerForm.password = "";
  registerForm.confirmPassword = "";
  registerForm.promoCode = "";
  registerForm.agreedTerms = false;
}

async function handleLoginSubmit() {
  if (!loginForm.account || !loginForm.password) {
    message.warning("请输入邮箱/用户名和密码");
    return;
  }
  loginLoading.value = true;
  try {
    const res = await apiLogin(loginForm.account, loginForm.password);
    auth.setAuth(res.token, res.user);
    const redirectPath = expiredSessionRedirectPath.value;
    expiredSessionRedirectPath.value = "";
    message.success("登录成功");
    loginModalVisible.value = false;
    resetAuthForms();
    await nextTick();
    await checkAnnouncement();
    await syncUserUnreadSystemMessageCount({ showToast: true, forceToast: true });
    startSystemMessagePolling();
    if (redirectPath && redirectPath !== route.fullPath) {
      await router.replace(redirectPath);
    }
  } catch (err: any) {
    message.error(err.response?.data?.detail || "登录失败");
  } finally {
    loginLoading.value = false;
  }
}

async function handleSendForgotPasswordCode() {
  if (!forgotPasswordForm.email) {
    message.warning("请输入邮箱");
    return;
  }
  if (!isValidEmail(forgotPasswordForm.email)) {
    message.warning("邮箱格式不正确");
    return;
  }
  forgotPasswordCodeLoading.value = true;
  try {
    forgotPasswordForm.verificationId = await sendPasswordResetEmailCode(forgotPasswordForm.email.trim());
    message.success("验证码已发送，请检查邮箱");
  } catch (err: any) {
    forgotPasswordForm.verificationId = "";
    message.error(err.message || "验证码发送失败");
  } finally {
    forgotPasswordCodeLoading.value = false;
  }
}

async function handleForgotPasswordSubmit() {
  if (!forgotPasswordForm.email || !forgotPasswordForm.verificationCode || !forgotPasswordForm.newPassword) {
    message.warning("请完整填写找回密码信息");
    return;
  }
  if (!isValidEmail(forgotPasswordForm.email)) {
    message.warning("邮箱格式不正确");
    return;
  }
  if (!/^\d{6}$/.test(forgotPasswordForm.verificationCode.trim())) {
    message.warning("请输入正确的 6 位验证码");
    return;
  }
  if (!forgotPasswordForm.verificationId) {
    message.warning("请先获取邮箱验证码");
    return;
  }
  if (forgotPasswordForm.newPassword.length < 6) {
    message.warning("新密码至少6位");
    return;
  }
  if (forgotPasswordForm.newPassword !== forgotPasswordForm.confirmPassword) {
    message.warning("两次密码不一致");
    return;
  }
  forgotPasswordLoading.value = true;
  try {
    await apiForgotPassword({
      email: forgotPasswordForm.email.trim(),
      verificationCode: forgotPasswordForm.verificationCode.trim(),
      verificationId: forgotPasswordForm.verificationId,
      newPassword: forgotPasswordForm.newPassword,
    });
    message.success("密码重置成功，请使用新密码登录");
    loginForm.account = forgotPasswordForm.email.trim();
    loginForm.password = "";
    resetForgotPasswordForm();
    authTab.value = "login";
    forgotPasswordDialogOpen.value = false;
    loginModalVisible.value = true;
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || "密码重置失败");
  } finally {
    forgotPasswordLoading.value = false;
  }
}

async function handleSendRegisterCode() {
  if (!registerForm.email) {
    message.warning("请输入邮箱");
    return;
  }
  if (!isValidEmail(registerForm.email)) {
    message.warning("邮箱格式不正确");
    return;
  }
  registerCodeLoading.value = true;
  try {
    await sendRegisterEmailCode(registerForm.email.trim());
    message.success("验证码已发送，请检查邮箱");
  } catch (err: any) {
    message.error(err.message || "验证码发送失败");
  } finally {
    registerCodeLoading.value = false;
  }
}

async function handleRegisterSubmit() {
  if (!registerForm.email || !registerForm.verificationCode || !registerForm.username || !registerForm.password) {
    message.warning("请完整填写注册信息");
    return;
  }
  if (!isValidEmail(registerForm.email)) {
    message.warning("邮箱格式不正确");
    return;
  }
  if (registerForm.password.length < 6) {
    message.warning("密码至少6位");
    return;
  }
  if (!/^\d{6}$/.test(registerForm.verificationCode.trim())) {
    message.warning("请输入正确的 6 位验证码");
    return;
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    message.warning("两次密码不一致");
    return;
  }
  const normalizedInviteOrPromoCode = normalizeInviteCode(showRegisterPromoCode ? registerForm.promoCode : "");
  const isPersonalInviteRegistration = isPersonalInviteCodeValue(normalizedInviteOrPromoCode);
  if (normalizedInviteOrPromoCode) {
    try {
      if (isPersonalInviteRegistration) {
        await validateInviteCode(normalizedInviteOrPromoCode);
      } else {
        await validatePromoCode(normalizedInviteOrPromoCode);
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || "邀请码无效");
      return;
    }
  }
  if (!registerForm.agreedTerms) {
    message.warning("请先阅读并同意用户协议和隐私政策");
    return;
  }
  registerLoading.value = true;
  try {
    await registerCloudbaseAccount(
      registerForm.email.trim(),
      registerForm.verificationCode.trim(),
      registerForm.password
    );
    const res = await apiRegister(
      registerForm.username.trim(),
      registerForm.email.trim(),
      registerForm.password,
      normalizedInviteOrPromoCode || undefined,
    );
    auth.setAuth(res.token, res.user);
    message.success("注册成功");
    if (isPersonalInviteRegistration) {
      clearStoredInviteCode();
    }
    notification.success({
      message: "赠送积分已到账",
      description: normalizedInviteOrPromoCode && !isPersonalInviteRegistration
        ? "新用户注册试用积分和推广码额外奖励积分已到账。"
        : isPersonalInviteRegistration
          ? "新用户注册试用积分已到账，邀请关系已绑定。"
          : "新用户注册试用积分已到账。",
      placement: "topRight",
      duration: 6,
    });
    loginModalVisible.value = false;
    resetAuthForms();
    await nextTick();
    await checkAnnouncement();
    await syncUserUnreadSystemMessageCount({ showToast: true, forceToast: true });
    startSystemMessagePolling();
  } catch (err: any) {
    message.error(err.response?.data?.detail || err.message || "注册失败");
  } finally {
    registerLoading.value = false;
  }
}

async function handleRedeemCredits() {
  const normalizedKey = redeemForm.key.trim().toUpperCase();
  if (!normalizedKey) {
    message.warning("请输入兑换码");
    return;
  }
  redeemLoading.value = true;
  try {
    const res = await redeemCreditKey(normalizedKey);
    try {
      auth.updateUser(await getMe());
    } catch {
      if (auth.user) {
        auth.updateUser({ ...auth.user, credits: res.credits });
      }
    }
    message.success(`兑换成功，已到账 ${res.credit_amount} 积分`);
    redeemDialogOpen.value = false;
    redeemForm.key = "";
  } catch (err: any) {
    message.error(err.response?.data?.detail || "兑换失败");
  } finally {
    redeemLoading.value = false;
  }
}

const creditsContactVisible = ref(false);
const contactQrImage = ref("");
const announcementVisible = ref(false);
const announcementDismissToday = ref(false);
const announcementConfig = ref<AnnouncementConfig>({
  announcement_enabled: false,
  announcement_content: "",
  announcement_updated_at: null,
});
const ANNOUNCEMENT_DISMISS_KEY = "systemAnnouncementDismissState";
const authInputPrefixStyle = { color: "var(--theme-input-prefix-color)" };

const avatarUrl = computed(() => auth.user?.avatar_url || "");
const avatarFallback = computed(() => auth.user?.username?.charAt(0)?.toUpperCase() || "U");

function getTodayString() {
  return new Date().toLocaleDateString("en-CA");
}

function getAnnouncementVersion(config: AnnouncementConfig) {
  return config.announcement_updated_at || "";
}

function shouldSuppressAnnouncement(config: AnnouncementConfig) {
  try {
    const raw = localStorage.getItem(ANNOUNCEMENT_DISMISS_KEY);
    if (!raw) return false;
    const parsed = JSON.parse(raw);
    return parsed?.date === getTodayString() && parsed?.version === getAnnouncementVersion(config);
  } catch {
    return false;
  }
}

function handleAnnouncementClose() {
  if (announcementDismissToday.value) {
    localStorage.setItem(ANNOUNCEMENT_DISMISS_KEY, JSON.stringify({
      date: getTodayString(),
      version: getAnnouncementVersion(announcementConfig.value),
    }));
  }
  announcementVisible.value = false;
}

async function checkAnnouncement() {
  try {
    const res = await getAnnouncementConfig();
    announcementConfig.value = res;
    if (!res.announcement_enabled || !res.announcement_content.trim() || shouldSuppressAnnouncement(res)) {
      return;
    }
    announcementDismissToday.value = false;
    announcementVisible.value = true;
  } catch {
    // ignore announcement config failures
  }
}

async function loadPaymentPlans() {
  if (!auth.isLoggedIn) return;
  purchasePlansLoading.value = true;
  try {
    const res = await listPaymentPlans();
    creditPurchasePlans.value = res.items;
    if (!res.items.some((item) => item.key === selectedPurchasePlanKey.value && item.purchasable)) {
      selectedPurchasePlanKey.value = "";
    }
    const firstPurchasablePlan = res.items.find((item) => item.purchasable);
    if (!selectedPurchasePlanKey.value && firstPurchasablePlan) {
      selectedPurchasePlanKey.value = firstPurchasablePlan.key;
    }
  } catch {
    creditPurchasePlans.value = [];
    selectedPurchasePlanKey.value = "";
  } finally {
    purchasePlansLoading.value = false;
  }
}

function handleSelectPurchasePlan(plan: PaymentPlan) {
  if (!plan.purchasable) return;
  selectedPurchasePlanKey.value = plan.key;
}

function resetPurchaseState() {
  purchaseLoading.value = false;
}

onMounted(async () => {
  unsubscribeAdminFeedbackCount = subscribeAdminUnresolvedFeedbackCount((count) => {
    adminUnresolvedFeedbackCount.value = count;
  });
  unsubscribeUserFeedbackCount = subscribeUserCompletedUnreadFeedbackCount((count) => {
    userCompletedUnreadFeedbackCount.value = count;
  });
  unsubscribeSystemMessageCount = subscribeUnreadSystemMessageCount((count) => {
    userUnreadSystemMessageCount.value = count;
  });
  unsubscribeAuthSessionExpired = subscribeAuthSessionExpired(handleAuthSessionExpired);

  if (typeof document !== "undefined") {
    themeObserver = new MutationObserver(() => {
      currentTheme.value = getCurrentTheme();
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: [APP_THEME_ATTRIBUTE],
    });
  }

  await Promise.allSettled([
    (async () => {
      const res = await getContactConfig();
      contactQrImage.value = res.contact_qr_image || "";
    })(),
    checkAnnouncement(),
    loadPaymentPlans(),
  ]);

  if (!auth.isLoggedIn) return;
  try {
    auth.updateUser(await getMe());
  } catch {
    // ignore sync failures for stale sessions
  }
  await syncAdminUnresolvedFeedbackCount();
  await syncUserCompletedUnreadFeedbackCount();
  await syncUserUnreadSystemMessageCount({ showToast: true, forceToast: true });
  startSystemMessagePolling();
});

onBeforeUnmount(() => {
  unsubscribeAdminFeedbackCount?.();
  unsubscribeAdminFeedbackCount = null;
  unsubscribeUserFeedbackCount?.();
  unsubscribeUserFeedbackCount = null;
  unsubscribeSystemMessageCount?.();
  unsubscribeSystemMessageCount = null;
  unsubscribeAuthSessionExpired?.();
  unsubscribeAuthSessionExpired = null;
  stopSystemMessagePolling();
  themeObserver?.disconnect();
  themeObserver = null;
});

function openCreditsContact() {
  mobileDrawerOpen.value = false;
  creditsContactVisible.value = true;
}

provide("openCreditsContact", openCreditsContact);
provide("openPurchaseEntry", openPurchaseEntry);

function openRedeemEntry() {
  mobileDrawerOpen.value = false;
  if (!auth.isLoggedIn) {
    openAuthModal("login");
    return;
  }
  redeemDialogOpen.value = true;
}

function openPurchaseEntry() {
  mobileDrawerOpen.value = false;
  if (!auth.isLoggedIn) {
    openAuthModal("login");
    return;
  }
  if (!creditPurchasePlans.value.length) {
    void loadPaymentPlans();
  }
  resetPurchaseState();
  purchaseDialogOpen.value = true;
}

async function handlePurchaseCredits() {
  const selectedPlan = creditPurchasePlans.value.find((item) => item.key === selectedPurchasePlanKey.value);
  if (!selectedPlan) return;
  purchaseLoading.value = true;
  const payWindow = window.open("", "_blank");
  try {
    const res = await createPaymentOrder(selectedPlan.key);
    if (payWindow) {
      payWindow.location.href = res.pay_url;
      purchaseDialogOpen.value = false;
      await router.push(`/payment-result?order_no=${encodeURIComponent(res.order_no)}`);
      return;
    }
    window.location.href = res.pay_url;
  } catch (err: any) {
    payWindow?.close();
    message.error(err.response?.data?.detail || "创建支付订单失败");
  } finally {
    purchaseLoading.value = false;
  }
}

function openPurchaseFeedbackDialog() {
  purchaseFeedbackForm.content = "";
  purchaseFeedbackDialogOpen.value = true;
}

function closePurchaseFeedbackDialog() {
  purchaseFeedbackDialogOpen.value = false;
}

async function handleSubmitPurchaseFeedback() {
  const normalized = purchaseFeedbackForm.content.trim();
  if (!normalized) {
    message.warning("请输入反馈内容");
    return;
  }

  const selectedPlan = creditPurchasePlans.value.find((item) => item.key === selectedPurchasePlanKey.value);
  const planText = selectedPlan ? `当前套餐：¥${selectedPlan.display_amount} / ${selectedPlan.credits}积分` : "当前套餐：未选择";
  purchaseFeedbackSubmitting.value = true;
  try {
    await createFeedback(null, `【积分购买反馈】\n${planText}\n\n${normalized}`);
    message.success("反馈已提交");
    closePurchaseFeedbackDialog();
  } catch (err: any) {
    message.error(err.response?.data?.detail || "提交反馈失败");
  } finally {
    purchaseFeedbackSubmitting.value = false;
  }
}

function openContactFromPurchaseFeedback() {
  purchaseFeedbackDialogOpen.value = false;
  openCreditsContact();
}

function goCreditLogs() {
  mobileDrawerOpen.value = false;
  router.push("/credit-logs");
}

function toggleMobileDrawer() {
  mobileDrawerOpen.value = !mobileDrawerOpen.value;
}

watch(
  () => route.fullPath,
  () => {
    mobileDrawerOpen.value = false;
  }
);

watch(
  () => [auth.isLoggedIn, auth.user?.role] as const,
  ([loggedIn]) => {
    if (!loggedIn) {
      creditPurchasePlans.value = [];
      selectedPurchasePlanKey.value = "";
      return;
    }
    void loadPaymentPlans();
  }
);

watch(purchaseDialogOpen, (open) => {
  if (!open) {
    resetPurchaseState();
  }
});

</script>

<template>
  <a-layout class="app-layout">
    <a-layout-header v-if="!hideTopMenu" class="app-header">
      <div class="header-inner">
        <div class="header-brand-wrap">
          <div class="header-brand" @click="router.push('/')">
            <div class="brand-mark">
              <img src="/香蕉.svg" alt="800AI" class="brand-mark-image" />
            </div>
            <div class="brand-copy">
              <span class="brand-name">800AI</span>
              <span class="brand-sub">AI Creative Studio</span>
            </div>
          </div>
          <a-button type="text" class="top-link-btn" @click="openCreditsContact">
            联系我们
          </a-button>
          <a-button type="text" class="top-link-btn" @click="openInviteRewardsEntry">
            邀请奖励
          </a-button>
          <div v-if="auth.isLoggedIn && isAdmin" class="desktop-admin-entry">
            <a-dropdown :trigger="['hover']" overlay-class-name="warm-dropdown">
              <a-badge :count="adminUnresolvedFeedbackCount" :offset="[-2, 2]" :show-zero="false">
                <a-button class="admin-btn" type="text" shape="circle" aria-label="admin-menu">
                  <template #icon><SettingOutlined /></template>
                </a-button>
              </a-badge>
              <template #overlay>
                <a-menu :selected-keys="adminSelectedKeys" @click="handleAdminMenu">
                  <a-menu-item
                    v-for="item in adminMenuBaseItems"
                    :key="item.key"
                  >
                    <component :is="item.icon" />
                    <span style="margin-left: 8px">{{ item.label }}</span>
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item
                    v-for="item in adminMenuBusinessItems"
                    :key="item.key"
                  >
                    <component :is="item.icon" />
                    <span style="margin-left: 8px">{{ item.label }}</span>
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item
                    v-for="item in adminMenuNoticeItems"
                    :key="item.key"
                    :class="{ 'admin-feedback-dropdown-item': item.key === '/admin/feedbacks' }"
                  >
                    <component :is="item.icon" />
                    <span v-if="item.key === '/admin/feedbacks'" class="admin-menu-feedback-label">
                      <span>{{ item.label }}</span>
                      <a-badge
                        v-if="hasAdminUnresolvedFeedback"
                        :count="adminUnresolvedFeedbackCount"
                        :number-style="{ backgroundColor: '#ff4d4f', color: '#fff' }"
                      />
                    </span>
                    <span v-else style="margin-left: 8px">{{ item.label }}</span>
                  </a-menu-item>
                  <template v-if="adminMenuConfigItems.length">
                    <a-menu-divider />
                    <a-menu-item
                      v-for="item in adminMenuConfigItems"
                      :key="item.key"
                    >
                      <component :is="item.icon" />
                      <span style="margin-left: 8px">{{ item.label }}</span>
                    </a-menu-item>
                  </template>
                </a-menu>
              </template>
            </a-dropdown>
          </div>
        </div>

        <div class="mobile-nav-entry">
          <div v-if="auth.isLoggedIn" class="mobile-nav-credits" @click="goCreditLogs">
            <ThunderboltOutlined />
            <span>{{ auth.user?.credits ?? 0 }}</span>
          </div>
          <a-button class="mobile-nav-fab" type="primary" shape="circle" @click="toggleMobileDrawer">
            <template #icon><MenuOutlined /></template>
          </a-button>
        </div>

        <a-menu
          mode="horizontal"
          :selected-keys="selectedKeys"
          class="header-menu"
          @click="handleMenuClick"
        >
          <a-menu-item v-for="item in primaryMenuItems" :key="item.key">
            <img :src="getPrimaryMenuIconSrc(item)" :alt="item.label" class="nav-menu-icon" />
            <span>{{ item.label }}</span>
          </a-menu-item>
        </a-menu>

        <div class="header-actions">
          <a-button type="text" class="top-link-btn" @click="openPurchaseEntry">
            购买积分
          </a-button>
          <a-button type="text" class="top-link-btn" @click="openRedeemEntry">
            兑换积分
          </a-button>
          <template v-if="auth.isLoggedIn">
            <div class="credits-badge" @click="goCreditLogs">
              <ThunderboltOutlined />
              <span>{{ auth.user?.credits ?? 0 }}</span>
            </div>

            <a-dropdown :trigger="['hover']" overlay-class-name="warm-dropdown">
              <a-badge
                dot
                :offset="[-2, 6]"
                :show-zero="false"
                :count="hasUserUnreadNotice ? 1 : 0"
                :dot-style="{ width: '12px', height: '12px', minWidth: '12px', boxShadow: '0 0 0 2px #fffdf8' }"
              >
                <div class="user-trigger">
                  <a-avatar :size="34" class="user-avatar" :src="avatarUrl || undefined">
                    {{ avatarFallback }}
                  </a-avatar>
                  <span class="user-name">{{ auth.user?.username }}</span>
                </div>
              </a-badge>
              <template #overlay>
                <a-menu @click="handleUserMenu">
                  <a-menu-item
                    v-for="item in userMenuAccountItems"
                    :key="item.key"
                  >
                    <component :is="item.icon" />
                    <span style="margin-left: 8px">{{ item.label }}</span>
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item
                    v-for="item in userMenuNoticeItems"
                    :key="item.key"
                    class="user-feedback-dropdown-item"
                  >
                    <component :is="item.icon" />
                    <span v-if="item.key === 'my-feedback'" class="user-menu-feedback-label">
                      <span>{{ item.label }}</span>
                      <a-badge
                        v-if="hasUserUnreadFeedback"
                        dot
                        :dot-style="{ width: '10px', height: '10px', minWidth: '10px' }"
                      />
                    </span>
                    <span v-else-if="item.key === 'system-messages'" class="user-menu-feedback-label">
                      <span>{{ item.label }}</span>
                      <a-badge
                        v-if="hasUserUnreadSystemMessage"
                        dot
                        :dot-style="{ width: '10px', height: '10px', minWidth: '10px' }"
                      />
                    </span>
                    <span v-else style="margin-left: 8px">{{ item.label }}</span>
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item
                    v-for="item in userMenuDangerItems"
                    :key="item.key"
                    danger
                  >
                    <component :is="item.icon" />
                    <span style="margin-left: 8px">{{ item.label }}</span>
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </template>

          <template v-else>
            <a-button type="primary" class="login-header-btn" @click="openAuthModal('login')">
              <template #icon><UserOutlined /></template>
              登录
            </a-button>
            <a-button class="register-header-btn" @click="openAuthModal('register')">
              <template #icon><UserAddOutlined /></template>
              注册
            </a-button>
          </template>
        </div>
      </div>
    </a-layout-header>

    <a-layout-content class="app-content">
      <div class="content-inner">
        <router-view v-slot="{ Component, route: currentRoute }">
          <transition :name="routeTransitionName" mode="out-in">
            <div :key="currentRoute.path" class="route-page-shell">
              <component :is="Component" />
            </div>
          </transition>
        </router-view>
      </div>
    </a-layout-content>

    <a-drawer
      v-if="!hideTopMenu"
      v-model:open="mobileDrawerOpen"
      placement="right"
      :width="320"
      class="mobile-nav-drawer"
      title="导航菜单"
    >
      <div class="mobile-drawer-content">
        <div class="mobile-drawer-brand">
          <div class="mobile-drawer-brand-main">
            <div class="brand-mark">
              <img src="/香蕉.svg" alt="800AI" class="brand-mark-image" />
            </div>
            <div class="brand-copy">
              <span class="brand-name">800AI</span>
              <span class="brand-sub">AI Creative Studio</span>
            </div>
          </div>
          <a-button type="link" size="small" class="mobile-drawer-contact-link" @click="openCreditsContact">
            联系我们
          </a-button>
        </div>

        <div v-if="auth.isLoggedIn" class="mobile-user-card">
          <a-avatar :size="48" class="user-avatar" :src="avatarUrl || undefined">
            {{ avatarFallback }}
          </a-avatar>
          <div class="mobile-user-meta">
            <span class="mobile-user-name">{{ auth.user?.username }}</span>
            <span class="mobile-user-role">
              {{ isSuperAdmin ? "超级管理员" : isAdmin ? "管理员" : "普通用户" }}
            </span>
          </div>
          <div class="mobile-user-actions">
            <div class="mobile-user-credits" @click="goCreditLogs">
              <ThunderboltOutlined />
              <span>{{ auth.user?.credits ?? 0 }}</span>
            </div>
          </div>
        </div>

        <div class="mobile-drawer-section">
          <div class="mobile-drawer-section-title">功能导航</div>
          <a-menu
            mode="inline"
            :selected-keys="selectedKeys"
            class="mobile-drawer-menu"
            @click="handleMenuClick"
          >
            <a-menu-item v-for="item in primaryMenuItems" :key="item.key">
              <img :src="getPrimaryMenuIconSrc(item)" :alt="item.label" class="nav-menu-icon" />
              <span>{{ item.label }}</span>
            </a-menu-item>
          </a-menu>
        </div>

        <div class="mobile-drawer-section">
          <div class="mobile-drawer-section-title">积分服务</div>
          <div class="mobile-drawer-credit-actions">
            <a-button block class="mobile-drawer-action-btn" @click="openPurchaseEntry">
              <template #icon><ThunderboltOutlined /></template>
              购买积分
            </a-button>
            <a-button block class="mobile-drawer-action-btn" @click="openRedeemEntry">
              <template #icon><GiftOutlined /></template>
              兑换积分
            </a-button>
          </div>
        </div>

        <div v-if="auth.isLoggedIn && isAdmin" class="mobile-drawer-section">
          <div class="mobile-drawer-section-title mobile-admin-section-title">
            <SettingOutlined />
            <a-badge
              v-if="hasAdminUnresolvedFeedback"
              :count="adminUnresolvedFeedbackCount"
              :number-style="{ backgroundColor: '#ff4d4f', color: '#fff' }"
            />
          </div>
          <a-menu
            mode="inline"
            :selected-keys="adminSelectedKeys"
            class="mobile-drawer-menu"
            @click="handleAdminMenu"
          >
            <a-menu-item v-for="item in adminMenuBaseItems" :key="item.key">
              <component :is="item.icon" />
              <span>{{ item.label }}</span>
            </a-menu-item>
            <a-menu-divider />
            <a-menu-item v-for="item in adminMenuBusinessItems" :key="item.key">
              <component :is="item.icon" />
              <span>{{ item.label }}</span>
            </a-menu-item>
            <a-menu-divider />
            <a-menu-item v-for="item in adminMenuNoticeItems" :key="item.key">
              <component :is="item.icon" />
              <span v-if="item.key === '/admin/feedbacks'" class="admin-menu-feedback-label">
                <span>{{ item.label }}</span>
                <a-badge
                  v-if="hasAdminUnresolvedFeedback"
                  :count="adminUnresolvedFeedbackCount"
                  :number-style="{ backgroundColor: '#ff4d4f', color: '#fff' }"
                />
              </span>
              <span v-else>{{ item.label }}</span>
            </a-menu-item>
            <template v-if="adminMenuConfigItems.length">
              <a-menu-divider />
              <a-menu-item v-for="item in adminMenuConfigItems" :key="item.key">
                <component :is="item.icon" />
                <span>{{ item.label }}</span>
              </a-menu-item>
            </template>
          </a-menu>
        </div>

        <div class="mobile-drawer-section">
          <div class="mobile-drawer-section-title">
            {{ auth.isLoggedIn ? "账户操作" : "账户入口" }}
          </div>

          <div v-if="auth.isLoggedIn">
            <a-menu mode="inline" class="mobile-drawer-menu" @click="handleUserMenu">
              <a-menu-item
                v-for="item in userMenuAccountItems"
                :key="item.key"
              >
                <component :is="item.icon" />
                <span>{{ item.label }}</span>
              </a-menu-item>
              <a-menu-divider />
              <a-menu-item
                v-for="item in userMenuNoticeItems"
                :key="item.key"
              >
                <component :is="item.icon" />
                <span v-if="item.key === 'my-feedback'" class="user-menu-feedback-label">
                  <span>{{ item.label }}</span>
                  <a-badge
                    v-if="hasUserUnreadFeedback"
                    dot
                    :dot-style="{ width: '10px', height: '10px', minWidth: '10px' }"
                  />
                </span>
                <span v-else-if="item.key === 'system-messages'" class="user-menu-feedback-label">
                  <span>{{ item.label }}</span>
                  <a-badge
                    v-if="hasUserUnreadSystemMessage"
                    dot
                    :dot-style="{ width: '10px', height: '10px', minWidth: '10px' }"
                  />
                </span>
                <span v-else>{{ item.label }}</span>
              </a-menu-item>
              <a-menu-divider />
              <a-menu-item
                v-for="item in userMenuDangerItems"
                :key="item.key"
                danger
              >
                <component :is="item.icon" />
                <span>{{ item.label }}</span>
              </a-menu-item>
            </a-menu>
          </div>
          <div v-else class="mobile-auth-actions">
            <a-button block class="mobile-drawer-guest-contact" @click="openCreditsContact">
              联系我们
            </a-button>
            <a-button type="primary" class="login-header-btn" block @click="openAuthModal('login')">
              <template #icon><UserOutlined /></template>
              登录
            </a-button>
            <a-button class="register-header-btn" block @click="openAuthModal('register')">
              <template #icon><UserAddOutlined /></template>
              注册
            </a-button>
          </div>
        </div>
      </div>
    </a-drawer>

    <a-modal
      v-model:open="creditsContactVisible"
      title="联系我们"
      :footer="null"
      :width="420"
      centered
    >
      <div class="credits-contact-modal">
        <div v-if="contactQrImage" class="credits-contact-qr">
          <img :src="contactQrImage" alt="contact qr code" />
        </div>
        <div v-else class="credits-contact-empty">
          暂未配置联系二维码，请联系管理员
        </div>
        <ul class="credits-contact-list">
          <li>积分获取</li>
          <li>API调用</li>
          <li>技术支持</li>
          <li>需求定制</li>
        </ul>
      </div>
    </a-modal>

    <a-modal
      v-model:open="purchaseDialogOpen"
      :footer="null"
      :width="520"
      centered
      wrap-class-name="credits-purchase-modal-wrap"
    >
      <template #title>
        <div class="credits-purchase-title">
          <span>积分套餐</span>
          <button type="button" class="credits-purchase-title-feedback" @click="openPurchaseFeedbackDialog">
            遇到问题？
          </button>
        </div>
      </template>
      <div class="credits-purchase-modal">
        <div class="credits-purchase-list">
          <button
            v-for="plan in creditPurchasePlans"
            :key="plan.key"
            type="button"
            class="credits-purchase-card"
            :class="[
              `credits-purchase-card-${plan.key}`,
              {
                'credits-purchase-card-active': plan.purchasable && selectedPurchasePlanKey === plan.key,
                'credits-purchase-card-disabled': !plan.purchasable,
              },
            ]"
            :disabled="!plan.purchasable"
            @click="handleSelectPurchasePlan(plan)"
          >
            <span v-if="plan.tag" class="credits-purchase-tag" :class="`credits-purchase-tag-${plan.key}`">{{ plan.tag }}</span>
            <div class="credits-purchase-price">
              <span class="credits-purchase-price-unit">¥</span>
              <span class="credits-purchase-price-value">{{ plan.display_amount }}</span>
            </div>
            <div class="credits-purchase-points">
              {{ plan.credits }} 积分
            </div>
            <div class="credits-purchase-name">
              <span>{{ plan.title }}</span>
              <span v-if="!plan.purchasable && plan.disabled_reason" class="credits-purchase-disabled-text">
                {{ plan.disabled_reason }}
              </span>
            </div>
            <div class="credits-purchase-check" :class="{ 'credits-purchase-check-active': plan.purchasable && selectedPurchasePlanKey === plan.key }">
              <CheckOutlined v-if="plan.purchasable && selectedPurchasePlanKey === plan.key" />
            </div>
          </button>
        </div>
        <div v-if="purchasePlansLoading" class="credits-purchase-safe-tip">正在加载积分套餐...</div>
        <div v-else-if="selectedPurchasePlan" class="credits-purchase-safe-tip">
          将跳转到支付宝收银台，实付 ¥{{ selectedPurchasePlan.display_amount }}，到账 {{ selectedPurchasePlan.credits }} 积分
        </div>
        <div v-else class="credits-purchase-safe-tip">暂未获取到可售积分套餐，请稍后再试</div>
        <a-button
          type="primary"
          block
          class="warm-primary-btn credits-purchase-submit"
          :loading="purchaseLoading"
          :disabled="purchasePlansLoading || !selectedPurchasePlan"
          @click="handlePurchaseCredits"
        >
          前往支付宝支付
        </a-button>
      </div>
    </a-modal>

    <a-modal
      v-model:open="purchaseFeedbackDialogOpen"
      title="提交反馈"
      :footer="null"
      :width="420"
      centered
      @cancel="closePurchaseFeedbackDialog"
    >
      <div class="purchase-feedback-modal">
        <a-form layout="vertical">
          <a-form-item label="问题描述" style="margin-bottom: 0">
            <a-textarea
              v-model:value="purchaseFeedbackForm.content"
              :rows="5"
              :maxlength="500"
              show-count
              placeholder="请描述你在积分购买时遇到的问题，我们会尽快处理"
            />
          </a-form-item>
        </a-form>
        <div class="purchase-feedback-hint">
          当前购买反馈入口已打开，你也可以通过
          <button type="button" class="purchase-feedback-contact-link" @click="openContactFromPurchaseFeedback">
            联系我们
          </button>
          获取更快支持。
        </div>
        <div class="purchase-feedback-actions">
          <a-button class="warm-secondary-btn" @click="closePurchaseFeedbackDialog">
            关闭
          </a-button>
          <a-button type="primary" class="warm-primary-btn" :loading="purchaseFeedbackSubmitting" @click="handleSubmitPurchaseFeedback">
            提交反馈
          </a-button>
        </div>
      </div>
    </a-modal>

    <a-modal
      v-model:open="announcementVisible"
      title="系统公告"
      :footer="null"
      :width="520"
      centered
      @cancel="handleAnnouncementClose"
    >
      <div class="announcement-modal">
        <div class="announcement-content">
          {{ announcementConfig.announcement_content }}
        </div>
        <a-checkbox v-model:checked="announcementDismissToday">
          今日不再弹出
        </a-checkbox>
        <div class="announcement-actions">
          <a-button type="primary" class="warm-primary-btn" @click="handleAnnouncementClose">
            知道了
          </a-button>
        </div>
      </div>
    </a-modal>

    <a-modal
      v-model:open="redeemDialogOpen"
      title="兑换积分"
      :confirm-loading="redeemLoading"
      :ok-button-props="{ class: 'warm-primary-btn' }"
      :cancel-button-props="{ class: 'warm-secondary-btn' }"
      ok-text="立即兑换"
      cancel-text="取消"
      centered
      :width="420"
      @ok="handleRedeemCredits"
    >
      <a-form layout="vertical" style="margin-top: 16px">
        <a-form-item label="兑换码" style="margin-bottom: 0">
          <a-input
            v-model:value="redeemForm.key"
            class="warm-input"
            :maxlength="16"
            placeholder="请输入 16 位兑换码"
            @press-enter="handleRedeemCredits"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="loginModalVisible"
      :title="null"
      :footer="null"
      :width="420"
      centered
      @after-close="resetAuthForms"
    >
      <a-tabs v-model:activeKey="authTab" centered class="auth-tabs">
        <a-tab-pane key="login" tab="登录">
          <a-form class="auth-form" layout="vertical" :model="loginForm" @finish="handleLoginSubmit">
            <a-form-item label="邮箱（推荐）/ 用户名">
              <a-input
                v-model:value="loginForm.account"
                size="large"
                placeholder="优先使用邮箱登录"
                :prefix="h(UserOutlined, { style: authInputPrefixStyle })"
              />
            </a-form-item>
            <a-form-item label="密码">
              <a-input-password
                v-model:value="loginForm.password"
                size="large"
                placeholder="请输入密码"
                :prefix="h(LockOutlined, { style: authInputPrefixStyle })"
                @press-enter="handleLoginSubmit"
              />
            </a-form-item>
            <div class="auth-row-action">
              <a @click="openForgotPasswordDialog">忘记密码？</a>
            </div>
            <a-form-item style="margin-bottom: 8px">
              <a-button
                type="primary"
                html-type="submit"
                size="large"
                :loading="loginLoading"
                block
                class="warm-primary-btn"
              >
                <template #icon><ThunderboltOutlined /></template>
                {{ loginLoading ? "登录中..." : "登录" }}
              </a-button>
            </a-form-item>
            <div class="auth-switch-hint">
              用户名重复时，请改用邮箱登录
            </div>
            <div class="auth-switch-hint" style="margin-top: 6px">
              还没有账号？<a @click="authTab = 'register'">立即注册</a>
            </div>
          </a-form>
        </a-tab-pane>

        <a-tab-pane key="register" tab="注册">
          <a-form class="auth-form" layout="vertical" :model="registerForm" @finish="handleRegisterSubmit">
            <a-form-item label="邮箱">
              <a-input
                v-model:value="registerForm.email"
                size="large"
                placeholder="请输入常用邮箱"
                :prefix="h(MailOutlined, { style: authInputPrefixStyle })"
                :maxlength="255"
              />
            </a-form-item>
            <a-form-item label="验证码">
              <div class="auth-code-row">
                <a-input
                  v-model:value="registerForm.verificationCode"
                  size="large"
                  placeholder="请输入 6 位验证码"
                  :maxlength="6"
                  @press-enter="handleRegisterSubmit"
                />
                <a-button
                  size="large"
                  class="auth-code-btn"
                  :loading="registerCodeLoading"
                  @click="handleSendRegisterCode"
                >
                  {{ registerCodeLoading ? "发送中..." : "发送验证码" }}
                </a-button>
              </div>
            </a-form-item>
            <a-form-item label="用户名">
              <a-input
                v-model:value="registerForm.username"
                size="large"
                placeholder="2-20 个字符"
                :prefix="h(UserOutlined, { style: authInputPrefixStyle })"
                :maxlength="20"
              />
            </a-form-item>
            <a-form-item label="密码">
              <a-input-password
                v-model:value="registerForm.password"
                size="large"
                placeholder="至少 6 位"
                :prefix="h(LockOutlined, { style: authInputPrefixStyle })"
              />
            </a-form-item>
            <a-form-item label="确认密码">
              <a-input-password
                v-model:value="registerForm.confirmPassword"
                size="large"
                placeholder="请再次输入密码"
                :prefix="h(LockOutlined, { style: authInputPrefixStyle })"
                @press-enter="handleRegisterSubmit"
              />
            </a-form-item>
            <a-form-item v-if="showRegisterPromoCode" label="邀请码（选填）">
              <a-input
                v-model:value="registerForm.promoCode"
                size="large"
                placeholder="填写邀请码（选填）"
                :maxlength="32"
              />
            </a-form-item>
            <a-form-item class="auth-agreement-item">
              <a-checkbox v-model:checked="registerForm.agreedTerms">
                我同意
                <RouterLink to="/user-agreement" target="_blank">用户协议</RouterLink>
                和
                <RouterLink to="/privacy-policy" target="_blank">隐私政策</RouterLink>
              </a-checkbox>
            </a-form-item>
            <a-form-item style="margin-bottom: 8px">
              <a-button
                type="primary"
                html-type="submit"
                size="large"
                :loading="registerLoading"
                :disabled="!registerForm.agreedTerms"
                block
                class="warm-primary-btn"
              >
                <template #icon><UserAddOutlined /></template>
                {{ registerLoading ? "注册中..." : "注册" }}
              </a-button>
            </a-form-item>
            <div class="auth-switch-hint">
              已有账号？<a @click="authTab = 'login'">去登录</a>
            </div>
          </a-form>
        </a-tab-pane>
      </a-tabs>
    </a-modal>

    <a-modal
      v-model:open="forgotPasswordDialogOpen"
      title="找回密码"
      :footer="null"
      :width="420"
      centered
      @after-close="resetForgotPasswordForm"
    >
      <a-form class="auth-form forgot-password-form" layout="vertical" :model="forgotPasswordForm" @finish="handleForgotPasswordSubmit">
        <a-form-item label="注册邮箱">
          <a-input
            v-model:value="forgotPasswordForm.email"
            size="large"
            placeholder="请输入注册邮箱"
            :prefix="h(MailOutlined, { style: authInputPrefixStyle })"
            :maxlength="255"
          />
        </a-form-item>
        <a-form-item label="验证码">
          <div class="auth-code-row">
            <a-input
              v-model:value="forgotPasswordForm.verificationCode"
              size="large"
              placeholder="请输入 6 位验证码"
              :maxlength="6"
            />
            <a-button
              size="large"
              class="auth-code-btn"
              :loading="forgotPasswordCodeLoading"
              @click="handleSendForgotPasswordCode"
            >
              {{ forgotPasswordCodeLoading ? "发送中..." : (forgotPasswordForm.verificationId ? "重新发送" : "发送验证码") }}
            </a-button>
          </div>
        </a-form-item>
        <a-form-item label="新密码">
          <a-input-password
            v-model:value="forgotPasswordForm.newPassword"
            size="large"
            placeholder="至少 6 位"
            :prefix="h(LockOutlined, { style: authInputPrefixStyle })"
          />
        </a-form-item>
        <a-form-item label="确认新密码">
          <a-input-password
            v-model:value="forgotPasswordForm.confirmPassword"
            size="large"
            placeholder="请再次输入新密码"
            :prefix="h(LockOutlined, { style: authInputPrefixStyle })"
            @press-enter="handleForgotPasswordSubmit"
          />
        </a-form-item>
        <a-form-item style="margin-bottom: 8px">
          <a-button
            type="primary"
            html-type="submit"
            size="large"
            :loading="forgotPasswordLoading"
            block
            class="warm-primary-btn"
          >
            <template #icon><LockOutlined /></template>
            {{ forgotPasswordLoading ? "重置中..." : "重置密码" }}
          </a-button>
        </a-form-item>
        <div class="auth-switch-hint">
          想起密码了？<a @click="forgotPasswordDialogOpen = false; authTab = 'login'; loginModalVisible = true">返回登录</a>
        </div>
      </a-form>
    </a-modal>
  </a-layout>
</template>

<style scoped lang="scss">
.app-layout {
  min-height: 100vh;
  background:
    radial-gradient(circle at top, var(--theme-page-glow), transparent 28%),
    var(--theme-page-gradient);
}

.app-header {
  background: var(--theme-header-bg) !important;
  box-shadow: 0 16px 32px var(--theme-header-shadow);
  padding: 0 24px !important;
  height: 74px;
  line-height: normal;
  position: sticky;
  top: 0;
  z-index: 1000;
  border-bottom: 1px solid var(--theme-header-border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.header-inner {
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0;
  height: 100%;
  background: transparent;
}

.header-brand-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  margin-right: 34px;
  flex-shrink: 0;
}

.brand-mark {
  width: 44px;
  height: 44px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgb(255, 171, 39);
  box-shadow: 0 12px 22px var(--theme-brand-shadow);
  overflow: hidden;
}

.brand-mark-image {
  width: 60%;
  height: 60%;
  object-fit: contain;
  display: block;
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--theme-title);
  letter-spacing: -0.2px;
}

.brand-sub {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--theme-subtitle);
}

.top-link-btn {
  height: 40px !important;
  padding-inline: 12px !important;
  font-weight: 700 !important;
  color: var(--theme-text-secondary) !important;
  border-radius: 999px !important;
}

.top-link-btn:hover,
.top-link-btn:focus {
  color: var(--theme-nav-hover-text) !important;
  background: var(--theme-nav-hover-bg) !important;
  border-color: transparent !important;
  box-shadow: none !important;
}

.header-menu {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  width: max-content;
  border-bottom: none !important;
  background: transparent;
  line-height: 54px;

  :deep(.ant-menu-item) {
    height: 46px;
    line-height: 46px;
    margin-inline: 4px !important;
    padding-inline: 16px !important;
    border-radius: 16px;
    font-weight: 700;
    color: var(--theme-nav-text);

    &::after {
      display: none;
    }
  }

  :deep(.ant-menu-item-selected) {
    background: rgb(255, 171, 39) !important;
    color: var(--theme-nav-active-text) !important;
    box-shadow: 0 10px 18px var(--theme-nav-active-shadow);
  }

  :deep(.ant-menu-item-selected .nav-menu-icon) {
    filter: var(--theme-nav-icon-active-filter);
  }

  :deep(.ant-menu-item:not(.ant-menu-item-selected):hover) {
    color: var(--theme-nav-hover-text) !important;
    background: var(--theme-nav-hover-bg) !important;
  }

  :deep(.ant-menu-title-content) {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
}

.nav-menu-icon {
  width: 20px;
  height: 20px;
  display: block;
  flex-shrink: 0;
  filter: var(--theme-nav-icon-filter);
  transition: filter var(--motion-duration-fast) var(--motion-ease-soft);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.mobile-nav-fab {
  width: 54px;
  height: 54px;
  display: none;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: none !important;
  background: var(--theme-accent) !important;
  box-shadow: 0 16px 30px var(--theme-fab-shadow);
}

.mobile-nav-entry {
  display: none;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.mobile-nav-credits {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 42px;
  padding: 0 14px;
  border-radius: 999px;
  background: var(--theme-pill-bg);
  border: 1px solid var(--theme-pill-border);
  color: var(--theme-pill-text);
  font-weight: 700;
  box-shadow: 0 10px 22px var(--theme-pill-shadow);
  cursor: pointer;
}

.mobile-drawer-credit-actions {
  display: grid;
  gap: 10px;
}

.mobile-drawer-action-btn {
  height: 44px;
  border-radius: 14px !important;
  border: 1px solid var(--theme-panel-border-strong) !important;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong)) !important;
  color: var(--theme-title) !important;
  font-weight: 700;
  text-align: left;
  box-shadow: 0 8px 18px var(--theme-card-shadow);

  &:hover,
  &:focus {
    color: var(--theme-nav-hover-text) !important;
    background: var(--theme-nav-hover-bg) !important;
    border-color: transparent !important;
    box-shadow: none !important;
  }
}

.mobile-drawer-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.mobile-drawer-brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mobile-drawer-brand-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.mobile-user-card {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 22px;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong));
  border: 1px solid var(--theme-panel-border-strong);
  box-shadow: 0 12px 24px var(--theme-card-shadow);
}

.mobile-user-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.mobile-user-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--theme-title);
  word-break: break-all;
}

.mobile-user-role {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.mobile-user-actions {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  align-self: stretch;
  gap: 8px;
  min-width: 0;
}

.mobile-drawer-contact-link {
  padding: 6px 12px !important;
  height: auto !important;
  border-radius: 16px !important;
  font-weight: 700;
  color: var(--theme-accent-text) !important;

  &:hover {
    color: var(--theme-nav-hover-text) !important;
    background: var(--theme-nav-hover-bg) !important;
  }
}

.mobile-user-credits {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--theme-pill-bg-strong);
  color: var(--theme-pill-text);
  font-weight: 700;
  cursor: pointer;
}

.mobile-drawer-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mobile-drawer-section-title {
  padding-left: 6px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--theme-subtitle);
  display: flex;
  align-items: center;
  gap: 8px;
}

.mobile-drawer-menu {
  border-inline-end: none !important;
  background: transparent !important;

  :deep(.ant-menu-item) {
    display: flex;
    align-items: center;
    height: 48px;
    line-height: 48px;
    margin: 4px 0 !important;
    border-radius: 16px;
    font-weight: 700;
    color: var(--theme-nav-text);
  }

  :deep(.ant-menu-title-content) {
    display: inline-flex;
    align-items: center;
    min-width: 0;
  }

  :deep(.ant-menu-item-selected) {
    background: rgb(255, 171, 39) !important;
    color: var(--theme-nav-active-text) !important;
    box-shadow: 0 10px 18px var(--theme-nav-active-shadow);
  }

  :deep(.ant-menu-item-selected .nav-menu-icon) {
    filter: var(--theme-nav-icon-active-filter);
  }

  :deep(.ant-menu-item-danger) {
    color: #c85a49 !important;
  }

  :deep(.ant-menu-item-danger:hover) {
    background: #fff1ee !important;
    color: #b84b3b !important;
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .app-layout {
  :deep(.ant-menu-item-danger:hover) {
    background: rgba(185, 56, 42, 0.14) !important;
    color: #de8f84 !important;
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .warm-dropdown .ant-dropdown-menu-item-danger:hover {
  background: rgba(185, 56, 42, 0.14) !important;
  color: #de8f84 !important;
}

.mobile-auth-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mobile-drawer-guest-contact {
  height: 48px !important;
  border-radius: 16px !important;
  font-weight: 700 !important;
  border: 1px solid var(--theme-panel-border-strong) !important;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong)) !important;
  color: var(--theme-title) !important;
  box-shadow: 0 8px 18px var(--theme-card-shadow);

  &:hover {
    color: var(--theme-nav-hover-text) !important;
    background: var(--theme-nav-hover-bg) !important;
    border-color: transparent !important;
    box-shadow: none !important;
  }
}

.admin-btn {
  height: 40px;
  width: 40px;
  padding-inline: 0;
  border-radius: 50%;
  border: 1px solid var(--theme-panel-border-strong) !important;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong)) !important;
  color: var(--theme-accent-text) !important;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 22px var(--theme-card-shadow);

  &:hover {
    color: var(--theme-accent-text-hover) !important;
    border-color: var(--theme-border-strong) !important;
    background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg-strong)) !important;
    box-shadow: 0 12px 24px var(--theme-card-shadow-strong);
  }
}

.desktop-admin-entry {
  display: inline-flex;
}

.admin-menu-feedback-label {
  margin-left: 8px;
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.admin-menu-feedback-label > span:first-child {
  min-width: 0;
  white-space: nowrap;
}

:deep(.admin-menu-feedback-label .ant-badge) {
  flex: 0 0 auto;
}

:deep(.admin-menu-feedback-label .ant-badge-count) {
  color: #fff !important;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 6px 6px;
  border-radius: 18px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
  border: 1px solid transparent;

  &:hover {
    background: var(--theme-panel-bg-muted);
    border-color: var(--theme-panel-border);
  }
}

.user-menu-feedback-label {
  margin-left: 8px;
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.user-menu-feedback-label > span:first-child {
  min-width: 0;
  white-space: nowrap;
}

.user-avatar {
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
  font-weight: 700;
  box-shadow: 0 10px 16px var(--theme-nav-active-shadow);
}

.user-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--theme-title);
}

.credits-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--theme-accent-text);
  cursor: pointer;
  transition: color 0.2s, transform 0.2s;

  &:hover {
    color: var(--theme-accent-text-hover);
    transform: translateY(-1px);
  }
}

.credits-contact-modal {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
  padding: 8px 0 4px;
  text-align: center;
}

.credits-contact-list {
  display: grid;
  grid-template-columns: repeat(2, auto);
  justify-content: center;
  justify-items: start;
  column-gap: 28px;
  row-gap: 8px;
  margin: 0 auto;
  width: max-content;
  max-width: 100%;
  padding: 0 0 0 1.15em;
  box-sizing: border-box;
  list-style: disc;
  list-style-position: outside;
  text-align: left;
  color: var(--theme-text-secondary);
  font-size: 14px;
  line-height: 1.6;

  li {
    display: list-item;

    &::marker {
      font-size: 0.75em;
      color: var(--theme-subtitle);
    }
  }
}

.credits-contact-qr {
  width: 240px;
  height: 240px;
  padding: 10px;
  border-radius: 24px;
  background: var(--theme-panel-bg-soft);
  border: 1px solid var(--theme-panel-border);
  box-shadow: inset 0 0 0 1px var(--theme-panel-inset);

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    border-radius: 18px;
    background: var(--theme-empty-bg);
  }
}

.credits-contact-empty {
  width: 100%;
  padding: 26px 18px;
  border-radius: 20px;
  background: var(--theme-panel-bg-soft);
  border: 1px dashed var(--theme-empty-border);
  color: var(--theme-text-secondary);
  line-height: 1.8;
}

.credits-purchase-modal {
  padding: 2px 2px 2px;
}

.credits-purchase-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.credits-purchase-title {
  position: relative;
  display: flex;
  align-items: center;
  padding-right: 56px;
}

.credits-purchase-title-feedback {
  position: absolute;
  right: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--theme-text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
}

.credits-purchase-title-feedback:hover {
  color: var(--theme-accent-text);
}

.credits-purchase-card {
  --credits-purchase-accent: #ff8a18;
  --credits-purchase-accent-start: #ff9a23;
  --credits-purchase-accent-end: #ff7a11;
  --credits-purchase-accent-shadow: rgba(255, 142, 31, 0.24);

  position: relative;
  display: grid;
  grid-template-columns: 90px minmax(82px, 0.72fr) minmax(128px, 1fr) auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 70px;
  padding: 14px;
  border-radius: 18px;
  border: 1.5px solid rgba(243, 154, 73, 0.24);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 248, 241, 0.94)),
    radial-gradient(circle at top, rgba(255, 214, 171, 0.34), transparent 62%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 10px 30px rgba(227, 150, 72, 0.08);
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.credits-purchase-card:hover {
  transform: translateY(-1px);
  border-color: rgba(244, 145, 53, 0.45);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 14px 36px rgba(227, 150, 72, 0.14);
}

.credits-purchase-card-active {
  border: 1px solid #ff8a18;
  background: #fff1e3;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 14px 30px var(--credits-purchase-accent-shadow);
}

.credits-purchase-card-disabled {
  border-color: rgba(183, 176, 168, 0.42);
  background:
    linear-gradient(180deg, rgba(248, 246, 243, 0.98), rgba(240, 237, 233, 0.96)),
    radial-gradient(circle at top, rgba(205, 205, 205, 0.16), transparent 62%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 6px 18px rgba(110, 104, 96, 0.08);
  cursor: not-allowed;
  opacity: 0.72;
}

.credits-purchase-card-disabled:hover {
  transform: none;
  border-color: rgba(183, 176, 168, 0.42);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 6px 18px rgba(110, 104, 96, 0.08);
}

.credits-purchase-tag {
  position: absolute;
  top: -9px;
  left: 14px;
  padding: 5px 11px;
  border-radius: 11px;
  background: linear-gradient(180deg, var(--credits-purchase-accent-start), var(--credits-purchase-accent-end));
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  box-shadow: 0 8px 16px var(--credits-purchase-accent-shadow);
}

.credits-purchase-card-starter {
  --credits-purchase-accent: #0ea5e9;
  --credits-purchase-accent-start: #38bdf8;
  --credits-purchase-accent-end: #0ea5e9;
  --credits-purchase-accent-shadow: rgba(14, 165, 233, 0.24);
}

.credits-purchase-card-light {
  --credits-purchase-accent: #ff8a18;
  --credits-purchase-accent-start: #ff9a23;
  --credits-purchase-accent-end: #ff7a11;
  --credits-purchase-accent-shadow: rgba(255, 142, 31, 0.24);
}

.credits-purchase-card-popular {
  --credits-purchase-accent: #ff8a18;
  --credits-purchase-accent-start: #ff9a23;
  --credits-purchase-accent-end: #ff7a11;
  --credits-purchase-accent-shadow: rgba(255, 142, 31, 0.24);
}

.credits-purchase-card-value {
  --credits-purchase-accent: #f43f5e;
  --credits-purchase-accent-start: #fb7185;
  --credits-purchase-accent-end: #f43f5e;
  --credits-purchase-accent-shadow: rgba(244, 63, 94, 0.24);
}

.credits-purchase-card-vip {
  --credits-purchase-accent: #7c3aed;
  --credits-purchase-accent-start: #a78bfa;
  --credits-purchase-accent-end: #7c3aed;
  --credits-purchase-accent-shadow: rgba(124, 58, 237, 0.28);
}

.credits-purchase-price {
  display: inline-flex;
  align-items: flex-end;
  gap: 6px;
  white-space: nowrap;
  color: #22252c;
}

.credits-purchase-price-value {
  font-size: 22px;
  font-weight: 500;
  line-height: 1;
}

.credits-purchase-price-unit {
  padding-bottom: 0;
  font-size: 12px;
  font-weight: 500;
  transform: translateY(1px);
}

.credits-purchase-points {
  display: flex;
  align-items: baseline;
  gap: 4px;
  flex-wrap: nowrap;
  font-size: 14px;
  font-weight: 700;
  color: #ff7a10;
  white-space: nowrap;
  min-width: 0;
}

.credits-purchase-name {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #76614f;
  white-space: nowrap;
}

.credits-purchase-disabled-text {
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
  color: #9a9188;
  white-space: normal;
}

.credits-purchase-check {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  justify-self: end;
  width: 24px;
  height: 24px;
  margin-left: 6px;
  border-radius: 999px;
  border: 1.5px solid #ecd9c9;
  color: transparent;
  background: rgba(255, 255, 255, 0.9);
  font-size: 12px;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    color 0.2s ease;
}

.credits-purchase-check-active {
  border-color: var(--credits-purchase-accent);
  background: linear-gradient(180deg, var(--credits-purchase-accent-start), var(--credits-purchase-accent-end));
  color: #fff;
  box-shadow: 0 10px 20px var(--credits-purchase-accent-shadow);
}

.credits-purchase-card-disabled .credits-purchase-price,
.credits-purchase-card-disabled .credits-purchase-points,
.credits-purchase-card-disabled .credits-purchase-name,
.credits-purchase-card-disabled .credits-purchase-check {
  color: #9a9188;
}

.credits-purchase-card-disabled .credits-purchase-check {
  border-color: #d8d0c7;
  background: rgba(255, 255, 255, 0.7);
}

.credits-purchase-card-disabled .credits-purchase-tag {
  background: linear-gradient(180deg, #c9c3bc, #afa79f);
  box-shadow: 0 8px 16px rgba(150, 142, 133, 0.18);
}

.credits-purchase-safe-tip {
  margin: 14px 0 12px;
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  color: #c69063;
}

.credits-purchase-submit {
  height: 46px !important;
}

.credits-purchase-qr-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 4px;
}

.credits-purchase-qr-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: center;
}

.credits-purchase-qr-subject {
  font-size: 18px;
  font-weight: 700;
  color: #3c2f23;
}

.credits-purchase-qr-meta {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.credits-purchase-qr-box {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 244px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(243, 154, 73, 0.2);
}

.credits-purchase-qr-box-empty {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.credits-purchase-qr-image {
  width: 220px;
  height: 220px;
  object-fit: contain;
}

.credits-purchase-qr-summary {
  display: grid;
  gap: 10px;
}

.credits-purchase-qr-summary div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 250, 245, 0.82);
  border: 1px solid rgba(243, 154, 73, 0.16);
}

.credits-purchase-qr-summary span {
  color: var(--theme-text-secondary);
}

.credits-purchase-qr-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.credits-purchase-qr-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 4px;
}

.credits-purchase-qr-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: center;
}

.credits-purchase-qr-subject {
  font-size: 18px;
  font-weight: 700;
  color: #3c2f23;
}

.credits-purchase-qr-meta {
  font-size: 12px;
  color: var(--theme-text-secondary);
}

.credits-purchase-qr-box {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 244px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(243, 154, 73, 0.2);
}

.credits-purchase-qr-box-empty {
  color: var(--theme-text-secondary);
  font-size: 13px;
}

.credits-purchase-qr-image {
  width: 220px;
  height: 220px;
  object-fit: contain;
}

.credits-purchase-qr-summary {
  display: grid;
  gap: 10px;
}

.credits-purchase-qr-summary div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 250, 245, 0.82);
  border: 1px solid rgba(243, 154, 73, 0.16);
}

.credits-purchase-qr-summary span {
  color: var(--theme-text-secondary);
}

.credits-purchase-qr-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.purchase-feedback-modal {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 8px;
}

.purchase-feedback-hint {
  font-size: 12px;
  line-height: 1.7;
  color: var(--theme-text-secondary);
}

.purchase-feedback-contact-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--theme-accent-text);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.purchase-feedback-contact-link:hover {
  color: var(--theme-accent-text-hover);
}

.purchase-feedback-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

:deep(.credits-purchase-modal-wrap .ant-modal-content) {
  border-radius: 22px;
  padding: 16px 18px 18px;
  background:
    radial-gradient(circle at top, rgba(255, 222, 183, 0.36), transparent 38%),
    linear-gradient(180deg, #fffdf9 0%, #fff9f1 100%);
  box-shadow:
    0 22px 60px rgba(83, 57, 28, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

:deep(.credits-purchase-modal-wrap .ant-modal-close) {
  top: 12px;
  right: 12px;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: rgba(255, 248, 240, 0.88);
  color: #b88c67;
}

:deep(.credits-purchase-modal-wrap .ant-modal-close:hover) {
  background: rgba(255, 241, 227, 0.96);
  color: #9f724d;
}

.announcement-modal {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 6px 0 2px;
}

.announcement-content {
  white-space: pre-wrap;
  line-height: 1.85;
  color: var(--theme-text);
  font-size: 14px;
  padding: 16px 18px;
  border-radius: 18px;
  background: var(--theme-panel-bg-soft);
  border: 1px solid var(--theme-panel-border);
}

.announcement-actions {
  display: flex;
  justify-content: flex-end;
}

.app-content {
  position: relative;
  padding: 22px 24px 28px;

  &::before {
    content: "";
    position: absolute;
    top: 0;
    right: 0;
    left: 0;
    height: 132px;
    pointer-events: none;
    background: linear-gradient(
      180deg,
      rgba(var(--theme-surface-strong-rgb), 0.72) 0%,
      rgba(var(--theme-surface-strong-rgb), 0.46) 34%,
      rgba(var(--theme-page-base-rgb), 0) 100%
    );
  }
}

.content-inner {
  max-width: 1400px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}

.route-page-shell {
  min-width: 0;
  background: transparent;
  border-radius: 0;
}

.route-page-forward-enter-active,
.route-page-forward-leave-active,
.route-page-back-enter-active,
.route-page-back-leave-active {
  transition:
    opacity var(--motion-duration-reveal-fast) var(--motion-ease-soft),
    transform var(--motion-duration-reveal) var(--motion-ease-enter);
}

.route-page-forward-enter-from {
  opacity: 0;
  transform: translate3d(18px, 0, 0);
}

.route-page-forward-leave-to {
  opacity: 0;
  transform: translate3d(-14px, 0, 0);
}

.route-page-back-enter-from {
  opacity: 0;
  transform: translate3d(-18px, 0, 0);
}

.route-page-back-leave-to {
  opacity: 0;
  transform: translate3d(14px, 0, 0);
}

.route-page-forward-enter-to,
.route-page-forward-leave-from,
.route-page-back-enter-to,
.route-page-back-leave-from {
  opacity: 1;
  transform: translate3d(0, 0, 0);
}

:deep(.mobile-nav-drawer .ant-drawer-header) {
  padding: 20px 20px 0;
  border-bottom: none;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
}

:deep(.mobile-nav-drawer .ant-drawer-title) {
  color: var(--theme-title);
  font-weight: 700;
}

:deep(.mobile-nav-drawer .ant-drawer-body) {
  padding: 18px 20px 24px;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-muted));
}

:deep(.ant-modal .ant-input-affix-wrapper),
:deep(.ant-modal .ant-input-password),
:deep(.ant-modal .ant-input) {
  border-radius: 14px;
}

:deep(.ant-modal .ant-btn-primary) {
  background: var(--theme-accent) !important;
  border: none !important;
}

.login-header-btn {
  height: 42px;
  padding-inline: 20px;
  border-radius: 999px;
  font-weight: 700;
  background: var(--theme-accent) !important;
  border: none !important;
  box-shadow: 0 10px 22px var(--theme-nav-active-shadow);
}

.register-header-btn {
  height: 42px;
  padding-inline: 20px;
  border-radius: 999px;
  font-weight: 700;
  border: 1px solid var(--theme-panel-border-strong) !important;
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong)) !important;
  color: var(--theme-accent-text) !important;
  box-shadow: 0 10px 22px var(--theme-card-shadow);

  &:hover {
    color: var(--theme-accent-text-hover) !important;
    border-color: var(--theme-border-strong) !important;
    background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg-strong)) !important;
  }
}

.auth-tabs {
  :deep(.ant-tabs-nav) {
    margin-bottom: 0;
  }

  :deep(.ant-tabs-tab) {
    font-weight: 700;
    font-size: 15px;
    color: var(--theme-text-muted);
  }

  :deep(.ant-tabs-tab-active .ant-tabs-tab-btn) {
    color: var(--theme-accent-text) !important;
  }

  :deep(.ant-tabs-ink-bar) {
    background: var(--theme-accent);
    height: 3px;
    border-radius: 2px;
  }
}

.auth-form {
  margin-top: 4px;

  :deep(.ant-form-item) {
    margin-bottom: 14px;
  }

  :deep(.ant-form-item-label) {
    padding-bottom: 4px;
  }

  :deep(.ant-form-item-label > label) {
    height: 20px;
    font-size: 13px;
  }

  .auth-agreement-item {
    margin-bottom: 10px;
  }
}

.auth-switch-hint {
  text-align: center;
  font-size: 13px;
  color: var(--theme-text-muted);

  a {
    color: var(--theme-link);
    font-weight: 600;
    cursor: pointer;

    &:hover {
      color: var(--theme-link-hover);
    }
  }
}

.auth-row-action {
  margin: -4px 0 12px;
  text-align: right;
  font-size: 13px;

  a {
    color: var(--theme-link);
    font-weight: 600;
    cursor: pointer;

    &:hover {
      color: var(--theme-link-hover);
    }
  }
}

.auth-code-row {
  display: flex;
  gap: 10px;

  > :first-child {
    flex: 1;
  }
}

.auth-code-btn {
  flex: 0 0 auto;
}

@media (max-width: 960px) {
  .app-header {
    padding-inline: 16px !important;
    height: auto;
  }

  .header-inner {
    gap: 12px;
    height: 74px;
    min-height: 74px;
  }

  .header-brand {
    margin-right: 0;
  }

  .header-brand-wrap {
    gap: 8px;
  }

  .top-link-btn {
    display: none;
  }

  .header-menu {
    display: none;
  }

  .header-actions {
    display: none;
  }

  .desktop-admin-entry {
    display: none;
  }

  .mobile-nav-entry {
    display: inline-flex;
  }

  .mobile-nav-fab {
    display: inline-flex;
  }
}

@media (max-width: 640px) {
  .brand-sub,
  .user-name {
    display: none;
  }

  .admin-btn {
    width: 38px;
    height: 38px;
  }

  .app-content {
    padding-inline: 14px;
  }

  :deep(.mobile-nav-drawer .ant-drawer-content-wrapper) {
    width: min(88vw, 320px) !important;
  }

  .credits-purchase-card {
    grid-template-columns: 1fr auto;
    gap: 6px 10px;
    padding: 14px 12px;
  }

  .credits-purchase-price,
  .credits-purchase-points,
  .credits-purchase-name {
    grid-column: 1 / 2;
  }

  .credits-purchase-check {
    grid-column: 2 / 3;
    grid-row: 1 / 4;
    align-self: center;
  }

  .credits-purchase-price-value {
    font-size: 19px;
  }

  .credits-purchase-points {
    font-size: 13px;
    white-space: normal;
  }

  .credits-purchase-name {
    font-size: 11px;
    white-space: normal;
  }

  .credits-purchase-safe-tip {
    margin: 14px 0 12px;
    font-size: 10px;
  }

  .credits-purchase-submit {
    height: 44px !important;
  }

  :deep(.credits-purchase-modal-wrap .ant-modal) {
    max-width: calc(100vw - 24px);
    margin: 0 auto;
  }

  :deep(.credits-purchase-modal-wrap .ant-modal-content) {
    padding: 16px 12px 16px;
    border-radius: 18px;
  }
}
</style>

<style lang="scss">
.warm-dropdown .ant-dropdown-menu {
  min-width: 176px;
  padding: 12px;
  border-radius: 18px;
  border: 1px solid var(--theme-panel-border);
  background: linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-soft));
  box-shadow: 0 16px 28px var(--theme-shadow-soft);
  color: var(--theme-title);
}

.warm-dropdown .ant-dropdown-menu,
.warm-dropdown .ant-dropdown-menu .ant-dropdown-menu-title-content,
.warm-dropdown .ant-dropdown-menu .ant-dropdown-menu-item,
.warm-dropdown .ant-dropdown-menu .ant-dropdown-menu-item span,
.warm-dropdown .ant-dropdown-menu .ant-dropdown-menu-item a,
.warm-dropdown .ant-dropdown-menu .ant-dropdown-menu-submenu-title,
.warm-dropdown .ant-dropdown-menu .ant-dropdown-menu-submenu-title span {
  color: var(--theme-title) !important;
}

.warm-dropdown .ant-dropdown-menu-item {
  display: flex;
  align-items: center;
  min-height: 50px;
  padding: 10px 16px;
  border-radius: 14px;
  color: var(--theme-title);
  font-weight: 700;
  gap: 8px;
  transition:
    background var(--motion-duration-fast) var(--motion-ease-soft),
    color var(--motion-duration-fast) var(--motion-ease-soft),
    box-shadow var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft);
}

.warm-dropdown .ant-dropdown-menu-item:hover {
  background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg-strong));
  color: var(--theme-accent-text-hover) !important;
  box-shadow: 0 10px 22px var(--theme-card-shadow);
  transform: translateY(-1px);
}

.warm-dropdown .ant-dropdown-menu-item:hover span,
.warm-dropdown .ant-dropdown-menu-item:hover a,
.warm-dropdown .ant-dropdown-menu-item:hover .ant-dropdown-menu-title-content {
  color: var(--theme-accent-text-hover) !important;
}

.warm-dropdown .ant-dropdown-menu-item-selected {
  background: var(--theme-accent) !important;
  color: var(--theme-accent-contrast) !important;
  box-shadow:
    inset 0 1px 0 var(--theme-panel-inset),
    0 10px 22px var(--theme-shadow-strong);
}

.warm-dropdown .ant-dropdown-menu-item-selected span,
.warm-dropdown .ant-dropdown-menu-item-selected a,
.warm-dropdown .ant-dropdown-menu-item-selected .ant-dropdown-menu-title-content {
  color: var(--theme-accent-contrast) !important;
}

.warm-dropdown .ant-dropdown-menu-item .anticon {
  font-size: 16px;
  color: currentColor;
}

.warm-dropdown .ant-dropdown-menu-item.admin-feedback-dropdown-item,
.warm-dropdown .ant-dropdown-menu-item.admin-feedback-dropdown-item .ant-dropdown-menu-title-content {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.warm-dropdown .ant-dropdown-menu-item.admin-feedback-dropdown-item .ant-dropdown-menu-title-content {
  min-width: 0;
  flex: 1 1 auto;
}

.warm-dropdown .ant-dropdown-menu-item.admin-feedback-dropdown-item .admin-menu-feedback-label {
  margin-left: 8px;
}

.warm-dropdown .ant-dropdown-menu-item.user-feedback-dropdown-item,
.warm-dropdown .ant-dropdown-menu-item.user-feedback-dropdown-item .ant-dropdown-menu-title-content {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.warm-dropdown .ant-dropdown-menu-item.user-feedback-dropdown-item .ant-dropdown-menu-title-content {
  min-width: 0;
  flex: 1 1 auto;
}

.warm-dropdown .ant-dropdown-menu-item-danger {
  color: #c85a49 !important;
}

.warm-dropdown .ant-dropdown-menu-item-danger span,
.warm-dropdown .ant-dropdown-menu-item-danger a,
.warm-dropdown .ant-dropdown-menu-item-danger .ant-dropdown-menu-title-content {
  color: inherit !important;
}

.warm-dropdown .ant-dropdown-menu-item-danger:hover {
  background: linear-gradient(180deg, #fff4f1, #ffede8) !important;
  color: #b84b3b !important;
}

.warm-dropdown .ant-dropdown-menu-item-divider {
  margin: 8px 2px;
  background: var(--theme-border);
}
</style>
