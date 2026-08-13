import client from "./client";
import type {
  AdminStats,
  AdminAnalyticsBreakdown,
  AdminErrorCategoryTimeseries,
  AdminErrorAnalytics,
  AdminErrorTaskList,
  ErrorTrendGranularity,
  AdminAnalyticsQuery,
  AdminAnalyticsRedeemRevenue,
  AdminAnalyticsSummary,
  AdminAnalyticsTimeseries,
  AdminConfig,
  CosConfig,
  AdminUser,
  AdminPaymentOrder,
  CreditLog,
  AdminRedeemKey,
  AdminRedeemKeyBatchResult,
  RedeemKeyStatus,
  ExternalApiConfig,
  ExternalApiConfigPayload,
  ExternalApiSecretConfig,
  ExternalApiSceneBinding,
  ExternalApiSceneBindingCreatePayload,
  ExternalApiSceneBindingMetaPayload,
  ExternalApiConfigStatus,
  ExternalApiConfigTestResult,
  AdminDailyReportTestResult,
  FeedbackDetail,
  FeedbackListResponse,
  FeedbackUnresolvedCountResponse,
  AdminFeedbackQuery,
  FeedbackUpdatePayload,
  HistoryFilter,
  HistoryResponse,
  UserHistoryCard,
  AdminUserPromoDashboard,
  AdminInviteRewardDashboard,
  AdminInviteRewardUserDetail,
  AdminPromoStatsDashboard,
  PromptOptimizeStyle,
  PromptOptimizeStylePayload,
  PromptOptimizeStyleStatus,
} from "@/types";

function buildAnalyticsParams(query: AdminAnalyticsQuery): Record<string, unknown> {
  const params: Record<string, unknown> = {
    granularity: query.granularity,
  };
  if (query.start_date) params.start_date = query.start_date;
  if (query.end_date) params.end_date = query.end_date;
  if (query.user_id) params.user_id = query.user_id;
  if (query.source) params.source = query.source;
  if (query.model) params.model = query.model;
  if (query.mode) params.mode = query.mode;
  if (query.status) params.status = query.status;
  return params;
}

export function listUsers(): Promise<AdminUser[]> {
  return client.get("/admin/users");
}

export function listUserOptions(): Promise<AdminUser[]> {
  return client.get("/admin/user-options");
}

export function getAdminUserDetail(userId: string): Promise<AdminUser> {
  return client.get(`/admin/users/${encodeURIComponent(userId)}`);
}

export function createUser(data: { username: string; password: string; role?: string }): Promise<AdminUser> {
  return client.post("/admin/users", data);
}

export function updateUserStatus(userId: string, status: string): Promise<AdminUser> {
  return client.put(`/admin/users/${userId}/status`, { status });
}

export function updateUserRole(userId: string, role: string): Promise<AdminUser> {
  return client.put(`/admin/users/${userId}/role`, { role });
}

export function updateUserWhitelist(userId: string, isWhitelisted: boolean): Promise<AdminUser> {
  return client.put(`/admin/users/${userId}/whitelist`, { is_whitelisted: isWhitelisted });
}

export function updateUserRemark(userId: string, remark: string): Promise<AdminUser> {
  return client.put(`/admin/users/${userId}/remark`, { remark });
}

export function resetUserPassword(userId: string, newPassword: string): Promise<AdminUser> {
  return client.put(`/admin/users/${userId}/reset-password`, { new_password: newPassword });
}

export function allocateCredits(userId: string, amount: number, description?: string): Promise<AdminUser> {
  return client.post(`/admin/users/${userId}/credits`, { amount, description: description || "" });
}

export function resetUserCredits(userId: string, description?: string): Promise<AdminUser> {
  return client.post(`/admin/users/${userId}/credits/reset`, { description: description || "" });
}

export function getUserPromoDashboard(userId: string): Promise<AdminUserPromoDashboard> {
  return client.get(`/admin/users/${userId}/promo-dashboard`);
}

export function getCreditLogs(
  page = 1,
  pageSize = 20,
  userId?: string,
  startDate?: string,
  endDate?: string,
  direction?: "increase" | "decrease",
  mode?: "text_generate" | "image_edit" | "inpaint" | "promptReverse" | "promptOptimize" | "manual" | "redeem" | "purchase",
): Promise<{ total: number; items: CreditLog[] }> {
  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (userId) params.user_id = userId;
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  if (direction) params.direction = direction;
  if (mode) params.mode = mode;
  return client.get("/admin/credit-logs", { params });
}

export function listPaymentOrders(params: {
  page?: number;
  page_size?: number;
  user?: string;
  status?: AdminPaymentOrder["status"];
  start_date?: string;
  end_date?: string;
}): Promise<{ total: number; items: AdminPaymentOrder[] }> {
  return client.get("/admin/payment-orders", { params });
}

export function createRedeemKeysBatch(count: number, creditAmount: number): Promise<AdminRedeemKeyBatchResult> {
  return client.post("/admin/redeem-keys/batch", {
    count,
    credit_amount: creditAmount,
  });
}

export function listRedeemKeys(params: {
  page?: number;
  page_size?: number;
  batch_no?: string;
  redeem_key?: string;
  credit_amount?: number;
  status?: RedeemKeyStatus;
  is_used?: boolean;
  used_by?: string;
  start_date?: string;
  end_date?: string;
}): Promise<{ total: number; items: AdminRedeemKey[] }> {
  return client.get("/admin/redeem-keys", { params });
}

export function updateRedeemKeyStatus(keyId: number, status: RedeemKeyStatus): Promise<AdminRedeemKey> {
  return client.post(`/admin/redeem-keys/${keyId}/status`, { status });
}

export function getStats(): Promise<AdminStats> {
  return client.get("/admin/stats");
}

export function getAdminInviteRewardDashboard(): Promise<AdminInviteRewardDashboard> {
  return client.get("/admin/invite-rewards");
}

export function getAdminInviteRewardUserDetail(userId: string): Promise<AdminInviteRewardUserDetail> {
  return client.get(`/admin/invite-rewards/users/${userId}`);
}

export function getAdminPromoStatsDashboard(): Promise<AdminPromoStatsDashboard> {
  return client.get("/admin/promo-stats");
}

export function getAdminPromoStatsUserDetail(userId: string): Promise<AdminUserPromoDashboard> {
  return client.get(`/admin/promo-stats/users/${userId}`);
}

export function getAdminHistory(
  page: number = 1,
  pageSize: number = 20,
  filter?: HistoryFilter,
): Promise<HistoryResponse> {
  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (filter?.status) params.status = filter.status;
  if (filter?.user_id) params.user_id = filter.user_id;
  if (filter?.source) params.source = filter.source;
  if (filter?.model) params.model = filter.model;
  if (filter?.mode) params.mode = filter.mode;
  if (filter?.start_date) params.start_date = filter.start_date;
  if (filter?.end_date) params.end_date = filter.end_date;
  return client.get("/admin/history", { params });
}

export function getAdminHistoryDetail(payload: {
  item_type: "task" | "prompt_history" | "prompt_optimize_task";
  task_id?: string | null;
  history_id?: number | null;
}): Promise<UserHistoryCard> {
  return client.get("/admin/history/detail", {
    params: {
      item_type: payload.item_type,
      task_id: payload.task_id || undefined,
      history_id: typeof payload.history_id === "number" ? payload.history_id : undefined,
    },
  });
}

export function getAdminHistoryCards(
  page: number = 1,
  pageSize: number = 20,
  filters: Pick<HistoryFilter, "mode" | "source" | "model" | "prompt" | "status" | "user_id" | "start_date" | "end_date" | "include_prompt_reverse" | "used_fallback_api"> = {},
): Promise<{ total: number; items: UserHistoryCard[] }> {
  return client.get("/admin/history/cards", {
    params: {
      page,
      page_size: pageSize,
      include_prompt_reverse: filters.include_prompt_reverse,
      mode: filters.mode,
      source: filters.source,
      model: filters.model,
      prompt: filters.prompt?.trim() || undefined,
      status: filters.status,
      user_id: filters.user_id,
      used_fallback_api: filters.used_fallback_api,
      start_date: filters.start_date,
      end_date: filters.end_date,
    },
  });
}

export function listAdminFeedbacks(
  page = 1,
  pageSize = 20,
  query?: AdminFeedbackQuery,
): Promise<FeedbackListResponse> {
  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (query?.feedback_id) params.feedback_id = query.feedback_id;
  if (query?.user_id) params.user_id = query.user_id;
  if (query?.task_id) params.task_id = query.task_id;
  if (query?.status) params.status = query.status;
  return client.get("/admin/feedback", { params });
}

export function getAdminUnresolvedFeedbackCount(): Promise<FeedbackUnresolvedCountResponse> {
  return client.get("/admin/feedback/unresolved-count");
}

export function getAdminFeedbackDetail(feedbackId: string): Promise<FeedbackDetail> {
  return client.get(`/admin/feedback/${feedbackId}`);
}

export function updateAdminFeedback(feedbackId: string, payload: FeedbackUpdatePayload): Promise<FeedbackDetail> {
  return client.patch(`/admin/feedback/${feedbackId}`, payload);
}

export function getAdminAnalyticsSummary(query: AdminAnalyticsQuery): Promise<AdminAnalyticsSummary> {
  return client.get("/admin/analytics/summary", { params: buildAnalyticsParams(query) });
}

export function getAdminAnalyticsTimeseries(query: AdminAnalyticsQuery): Promise<AdminAnalyticsTimeseries> {
  return client.get("/admin/analytics/timeseries", { params: buildAnalyticsParams(query) });
}

export function getAdminAnalyticsBreakdown(query: AdminAnalyticsQuery): Promise<AdminAnalyticsBreakdown> {
  return client.get("/admin/analytics/breakdown", { params: buildAnalyticsParams(query) });
}

export function getAdminAnalyticsRedeemRevenue(query: AdminAnalyticsQuery): Promise<AdminAnalyticsRedeemRevenue> {
  return client.get("/admin/analytics/redeem-revenue", {
    params: {
      granularity: query.granularity,
      start_date: query.start_date,
      end_date: query.end_date,
    },
  });
}

export function getAdminAnalyticsPaymentRevenue(query: AdminAnalyticsQuery): Promise<AdminAnalyticsRedeemRevenue> {
  return client.get("/admin/analytics/payment-revenue", {
    params: {
      granularity: query.granularity,
      start_date: query.start_date,
      end_date: query.end_date,
    },
  });
}

export function getAdminErrorAnalytics(params: {
  start_date?: string;
  end_date?: string;
  model?: string;
  error_category?: string;
  used_fallback_api?: boolean;
}): Promise<AdminErrorAnalytics> {
  return client.get("/admin/analytics/errors", { params });
}

export function getAdminErrorCategoryTimeseries(query: {
  granularity: ErrorTrendGranularity;
  start_date?: string;
  end_date?: string;
  model?: string;
  used_fallback_api?: boolean;
  limit?: number;
}): Promise<AdminErrorCategoryTimeseries> {
  return client.get("/admin/analytics/errors/timeseries", { params: query });
}

export function getAdminErrorTasks(params: {
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  model?: string;
  error_category?: string;
  used_fallback_api?: boolean;
}): Promise<AdminErrorTaskList> {
  return client.get("/admin/analytics/errors/tasks", { params });
}

export function getAdminConfig(): Promise<AdminConfig | null> {
  return client.get("/admin/api-key");
}

export function setAdminConfig(payload: {
  contact_qr_image?: string;
  announcement_enabled?: boolean;
  announcement_content?: string;
}): Promise<AdminConfig> {
  return client.put("/admin/api-key", payload);
}

export function deleteAdminConfig(): Promise<void> {
  return client.delete("/admin/api-key");
}

export function testAdminDailyReportNotify(): Promise<AdminDailyReportTestResult> {
  return client.post("/admin/notify/daily-report/test");
}

export function getExternalApiSecrets(): Promise<ExternalApiSecretConfig | null> {
  return client.get("/admin/external-api-secrets");
}

export function setExternalApiSecrets(payload: {
  key?: string;
  tongyi_key?: string;
}): Promise<ExternalApiSecretConfig> {
  return client.put("/admin/external-api-secrets", payload);
}

export function getCosConfig(): Promise<CosConfig | null> {
  return client.get("/admin/cos-config");
}

export function setCosConfig(payload: {
  cos_secret_id?: string;
  cos_secret_key?: string;
  cos_bucket?: string;
  cos_region?: string;
  cos_public_base_url?: string;
}): Promise<CosConfig> {
  return client.put("/admin/cos-config", payload);
}

export function deleteCosConfig(): Promise<void> {
  return client.delete("/admin/cos-config");
}

export function listExternalApiConfigs(): Promise<ExternalApiConfig[]> {
  return client.get("/admin/external-api-configs");
}

export function createExternalApiConfig(payload: ExternalApiConfigPayload): Promise<ExternalApiConfig> {
  return client.post("/admin/external-api-configs", payload);
}

export function updateExternalApiConfig(configId: number, payload: ExternalApiConfigPayload): Promise<ExternalApiConfig> {
  return client.put(`/admin/external-api-configs/${configId}`, payload);
}

export function updateExternalApiConfigStatus(configId: number, status: ExternalApiConfigStatus): Promise<ExternalApiConfig> {
  return client.patch(`/admin/external-api-configs/${configId}/status`, { status });
}

export function deleteExternalApiConfig(configId: number): Promise<void> {
  return client.delete(`/admin/external-api-configs/${configId}`);
}

export function listExternalApiSceneBindings(): Promise<ExternalApiSceneBinding[]> {
  return client.get("/admin/external-api-scene-bindings");
}

export function createExternalApiSceneBinding(
  payload: ExternalApiSceneBindingCreatePayload,
): Promise<ExternalApiSceneBinding> {
  return client.post("/admin/external-api-scene-bindings", payload);
}

export function updateExternalApiSceneBindingMeta(
  sceneKey: ExternalApiSceneBinding["scene_key"],
  payload: ExternalApiSceneBindingMetaPayload,
): Promise<ExternalApiSceneBinding> {
  return client.patch(`/admin/external-api-scene-bindings/${sceneKey}/meta`, payload);
}

export function updateExternalApiSceneBindingStatus(
  sceneKey: ExternalApiSceneBinding["scene_key"],
  status: ExternalApiConfigStatus,
): Promise<ExternalApiSceneBinding> {
  return client.patch(`/admin/external-api-scene-bindings/${sceneKey}/status`, { status });
}

export function deleteExternalApiSceneBinding(
  sceneKey: ExternalApiSceneBinding["scene_key"],
): Promise<void> {
  return client.delete(`/admin/external-api-scene-bindings/${sceneKey}`);
}

export function listPromptOptimizeStyles(): Promise<PromptOptimizeStyle[]> {
  return client.get("/admin/prompt-optimize-styles");
}

export function createPromptOptimizeStyle(payload: PromptOptimizeStylePayload): Promise<PromptOptimizeStyle> {
  return client.post("/admin/prompt-optimize-styles", payload);
}

export function updatePromptOptimizeStyle(styleId: number, payload: PromptOptimizeStylePayload): Promise<PromptOptimizeStyle> {
  return client.put(`/admin/prompt-optimize-styles/${styleId}`, payload);
}

export function updatePromptOptimizeStyleStatus(styleId: number, status: PromptOptimizeStyleStatus): Promise<PromptOptimizeStyle> {
  return client.patch(`/admin/prompt-optimize-styles/${styleId}/status`, { status });
}

export function setPromptOptimizeStyleDefault(styleId: number): Promise<PromptOptimizeStyle> {
  return client.post(`/admin/prompt-optimize-styles/${styleId}/set-default`);
}

export function deletePromptOptimizeStyle(styleId: number): Promise<void> {
  return client.delete(`/admin/prompt-optimize-styles/${styleId}`);
}

export function updateExternalApiSceneBinding(
  sceneKey: ExternalApiSceneBinding["scene_key"],
  payload: {
    api_config_id: number | null;
    backup_api_config_id: number | null;
    credit_cost: number;
    resolution_credit_costs_json: string;
    display_name: string;
    subtitle: string;
  },
): Promise<ExternalApiSceneBinding> {
  return client.put(`/admin/external-api-scene-bindings/${sceneKey}`, payload);
}

export function testExternalApiConfig(payload: ExternalApiConfigPayload): Promise<ExternalApiConfigTestResult> {
  return client.post("/admin/external-api-configs/test", payload);
}
