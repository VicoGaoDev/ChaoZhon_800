export interface UserInfo {
  id: string;
  business_id: string;
  username: string;
  email?: string | null;
  role: "user" | "admin" | "superadmin";
  avatar_url?: string;
  credits: number;
  is_whitelisted: boolean;
}

export interface LoginResponse {
  token: string;
  user: UserInfo;
}

export type UserApiKeyStatus = "enabled" | "disabled";

export interface UserApiKey {
  id: number;
  expire_time?: string | null;
  api_key: string;
  key_name: string;
  status: UserApiKeyStatus;
  is_delete: boolean;
  key_prefix: string;
  key_last4: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PromptHistoryItem {
  id: number;
  prompt: string;
  mode: "generate" | "inpaint" | "promptReverse" | "promptOptimize";
  source_image: string;
  created_at: string;
}

export interface ImageResult {
  id: number;
  image_url: string;
  preview_url?: string;
  thumb_url?: string;
  status: "pending" | "success" | "failed";
  error_message?: string;
  image_format?: string;
  image_size_bytes?: number;
  is_deleted?: boolean;
}

export type TaskMode = "generate" | "inpaint" | "promptReverse" | "promptOptimize";
export type TaskType = "text_generate" | "image_edit" | "inpaint" | "promptReverse" | "promptOptimize";
export type TaskSource = "web" | "app" | "api";
export type HistoryItemType = "task" | "prompt_history" | "prompt_optimize_task";

export interface TaskResult {
  id: string;
  model: string;
  source: TaskSource;
  prompt: string;
  num_images: number;
  size: string;
  resolution: string;
  custom_size?: string;
  credit_cost: number;
  credit_refunded?: boolean;
  status: "pending" | "queued" | "processing" | "success" | "failed";
  error_message?: string;
  created_at: string;
  enqueued_at?: string | null;
  request_started_at?: string | null;
  request_finished_at?: string | null;
  images: ImageResult[];
}

export interface HistoryItem {
  item_type: HistoryItemType;
  task_id?: string | null;
  history_id?: number | null;
  style_id?: number | null;
  style_name?: string;
  display_id?: string;
  user_id?: string;
  username?: string;
  avatar_url?: string;
  task_type: TaskType;
  model: string;
  source: TaskSource;
  mode: TaskMode;
  prompt: string;
  reference_images: string[];
  num_images: number;
  size: string;
  resolution: string;
  custom_size?: string;
  credit_cost: number;
  credit_refunded?: boolean;
  used_fallback_api?: boolean;
  status: string;
  error_message?: string;
  task_is_deleted?: boolean;
  is_soft_deleted?: boolean;
  soft_deleted_count?: number;
  created_at: string;
  images: ImageResult[];
  api_attempts?: TaskApiAttempt[];
}

export interface HistoryFilter {
  mode?: TaskType;
  source?: TaskSource;
  model?: string;
  prompt?: string;
  status?: string;
  user_id?: string;
  start_date?: string;
  end_date?: string;
  used_fallback_api?: boolean;
  respect_pins?: boolean;
  include_prompt_reverse?: boolean;
}

export interface HistoryResponse {
  total: number;
  total_credit_cost: number;
  items: HistoryItem[];
}

export interface TaskApiAttempt {
  id?: number | null;
  image_id?: number | null;
  image_index?: number | null;
  api_config_id?: number | null;
  api_config_name: string;
  attempt_index: number;
  is_fallback: boolean;
  status: "success" | "failed" | string;
  http_status?: number | null;
  error_message?: string;
  duration_ms?: number | null;
  created_at?: string | null;
  request_preview?: {
    request_url: string;
    headers: Record<string, string>;
    payload: unknown;
  } | null;
}

export interface UserHistoryCard {
  history_id?: number | null;
  item_type: HistoryItemType;
  style_id?: number | null;
  style_name?: string;
  display_id?: string;
  task_id?: string | null;
  image_id?: number | null;
  user_id?: string;
  username?: string;
  avatar_url?: string;
  is_pinned: boolean;
  pinned_at?: string | null;
  image_url: string;
  preview_url?: string;
  thumb_url?: string;
  status: "pending" | "queued" | "processing" | "success" | "failed";
  image_format?: string;
  image_size_bytes?: number;
  task_is_deleted?: boolean;
  is_soft_deleted?: boolean;
  task_type: TaskType;
  model: string;
  source: TaskSource;
  mode: TaskMode;
  prompt: string;
  reference_images: string[];
  reference_image_thumbs: string[];
  source_image: string;
  source_image_thumb: string;
  mask_image: string;
  mask_image_thumb: string;
  num_images: number;
  size: string;
  resolution: string;
  custom_size?: string;
  credit_cost: number;
  credit_refunded?: boolean;
  used_fallback_api?: boolean;
  created_at: string;
  run_time?: number | null;
  error_message?: string;
  images: ImageResult[];
  api_attempts?: TaskApiAttempt[];
}

export interface UserHistoryResponse {
  total: number;
  items: UserHistoryCard[];
}

export interface UserAssetCategory {
  id: number;
  name: string;
  sort_order: number;
  asset_count: number;
  preview_urls: string[];
  updated_at?: string | null;
}

export interface UserAssetCategoryListResponse {
  items: UserAssetCategory[];
  uncategorized_count: number;
}

export interface UserAssetQuota {
  used: number;
  limit: number;
  remaining: number;
}

export interface UserAsset {
  id: number;
  category_id?: number | null;
  category_name: string;
  file_name: string;
  image_url: string;
  thumb_url: string;
  mime_type: string;
  file_size: number;
  width?: number | null;
  height?: number | null;
  status: string;
  created_at?: string | null;
  completed_at?: string | null;
}

export interface UserAssetListResponse {
  items: UserAsset[];
  total: number;
  quota: UserAssetQuota;
}

export interface HistoryPinTogglePayload {
  item_type: HistoryItemType;
  image_id?: number | null;
  history_id?: number | null;
}

export interface HistoryPinToggleResponse {
  is_pinned: boolean;
  pinned_at?: string | null;
}

export type FeedbackStatus = "pending" | "processing" | "completed";

export interface FeedbackTaskSummary {
  task_id: string;
  model: string;
  mode: TaskMode;
  task_type: TaskType;
  source: TaskSource;
  prompt: string;
  status: string;
  error_message?: string;
  credit_refunded?: boolean;
  created_at?: string | null;
  reference_images: string[];
  reference_image_thumbs: string[];
  images: ImageResult[];
}

export interface FeedbackItem {
  feedback_id: string;
  user_id: string;
  username: string;
  task_id: string;
  status: FeedbackStatus;
  is_read: boolean;
  content: string;
  process_note: string;
  result_note: string;
  handler_id?: string | null;
  handler_name: string;
  handled_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  task: FeedbackTaskSummary;
}

export interface FeedbackDetail extends FeedbackItem {
  task_user_id: string;
}

export interface FeedbackListResponse {
  total: number;
  items: FeedbackItem[];
}

export interface FeedbackUnresolvedCountResponse {
  count: number;
}

export interface FeedbackReadCountResponse {
  count: number;
}

export interface FeedbackListQuery {
  task_id?: string;
  status?: FeedbackStatus;
}

export interface FeedbackUpdatePayload {
  status?: FeedbackStatus;
  process_note?: string;
  result_note?: string;
}

export interface AdminFeedbackQuery extends FeedbackListQuery {
  user_id?: string;
  feedback_id?: string;
}

export interface SystemMessageSender {
  user_id: string;
  username: string;
}

export interface SystemMessageRecipient {
  user_id: string;
  username: string;
  email?: string | null;
  is_read: boolean;
  read_at?: string | null;
}

export type SystemMessageRecipientScope = "selected" | "all";

export interface SystemMessageItem {
  message_id: string;
  subject: string;
  content_text: string;
  sender: SystemMessageSender;
  recipient_scope: SystemMessageRecipientScope;
  recipient_count: number;
  is_read: boolean;
  read_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SystemMessageDetail extends SystemMessageItem {
  content_html: string;
  recipients?: SystemMessageRecipient[];
}

export interface SystemMessageListResponse {
  total: number;
  items: SystemMessageItem[];
}

export interface SystemMessageReadCountResponse {
  count: number;
}

export interface SystemMessageCreatePayload {
  subject: string;
  content_html: string;
  recipient_scope: SystemMessageRecipientScope;
  recipient_user_ids: string[];
}

export type PromptOptimizeStyleStatus = "enabled" | "disabled";

export interface PromptOptimizeStyle {
  id: number;
  name: string;
  description: string;
  style_prompt: string;
  sort_order: number;
  status: PromptOptimizeStyleStatus;
  is_default: boolean;
  is_deleted?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  usage_count?: number;
}

export interface PromptOptimizeStylePayload {
  name: string;
  description: string;
  style_prompt: string;
  sort_order: number;
  status: PromptOptimizeStyleStatus;
  is_default: boolean;
}

export interface PublicPromptOptimizeStyle {
  id: number;
  name: string;
  description: string;
  style_prompt: string;
  is_default: boolean;
  sort_order: number;
}

export interface AdminUser {
  id: string;
  username: string;
  email?: string | null;
  avatar_url?: string;
  role: string;
  status: string;
  is_whitelisted: boolean;
  remark?: string;
  credits: number;
  consumed_credits: number;
  created_at: string;
}

export interface AdminUserPromoDashboard {
  user_id: string;
  username: string;
  summary: PromoCodeSummary;
  promo_codes: PromoCodeItem[];
  referrals: PromoReferralItem[];
  activities: PromoReferralActivityItem[];
}

export interface CreditLog {
  id: number;
  user_id: string;
  username: string;
  amount: number;
  type: "allocate" | "consume";
  mode: TaskType | "manual" | "redeem" | "purchase";
  description: string;
  operator_name: string;
  task_id?: string;
  created_at: string;
}

export interface PaymentPlan {
  key: string;
  title: string;
  amount_fen: number;
  display_amount: string;
  credits: number;
  tag: string;
  purchasable: boolean;
  disabled_reason: string;
}

export interface PaymentOrder {
  order_no: string;
  plan_key: string;
  subject: string;
  amount_fen: number;
  credits: number;
  status: "created" | "pending_pay" | "paid" | "credited" | "closed" | "failed";
  paid_at?: string | null;
  credited_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CreatePaymentOrderResult {
  order_no: string;
  status: "created" | "pending_pay" | "paid" | "credited" | "closed" | "failed";
  amount_fen: number;
  credits: number;
  subject: string;
  pay_url: string;
}

export type RedeemKeyStatus = "enabled" | "disabled";

export interface RedeemCreditResult {
  message: string;
  credit_amount: number;
  credits: number;
  redeem_key: string;
  used_at?: string | null;
}

export interface PromoCodeSummary {
  total_referrals: number;
  used_code_count: number;
  rewarded_registrations: number;
}

export interface PromoCodeItem {
  id: number;
  code: string;
  platform_name: string;
  status: string;
  created_at?: string | null;
  referral_count: number;
}

export interface PromoCodeListResponse {
  summary: PromoCodeSummary;
  items: PromoCodeItem[];
}

export interface PromoReferralItem {
  user_id: string;
  username: string;
  email_masked: string;
  email?: string | null;
  promo_code: string;
  platform_name: string;
  reward_credits: number;
  registered_at?: string | null;
}

export interface PromoReferralListResponse {
  total: number;
  items: PromoReferralItem[];
}

export interface PromoReferralActivityItem {
  user_id: string;
  username: string;
  email_masked: string;
  activity_type: "purchase" | "redeem";
  credits: number;
  amount_fen?: number | null;
  amount_yuan?: number | null;
  redeem_key: string;
  order_no: string;
  occurred_at?: string | null;
}

export interface PromoReferralActivityListResponse {
  total: number;
  items: PromoReferralActivityItem[];
}

export interface InviteRewardSummary {
  total_referrals: number;
  today_referrals: number;
  rewarded_invitees: number;
  reward_grant_count: number;
  total_reward_credits: number;
  today_reward_credits: number;
}

export interface InviteRewardOverviewResponse {
  invite_code: string;
  invite_link: string;
  reward_rate: number;
  max_reward_count: number;
  summary: InviteRewardSummary;
}

export interface InviteRewardReferralItem {
  user_id: string;
  username: string;
  email_masked: string;
  reward_count: number;
  total_reward_credits: number;
  last_reward_at?: string | null;
  registered_at?: string | null;
}

export interface InviteRewardReferralListResponse {
  total: number;
  items: InviteRewardReferralItem[];
}

export interface InviteRewardLogItem {
  id: number;
  invitee_user_id: string;
  invitee_username: string;
  invitee_email_masked: string;
  source_type: "payment" | "redeem" | string;
  source_id: string;
  source_credits: number;
  reward_rate: number;
  reward_credits: number;
  reward_index: number;
  created_at?: string | null;
}

export interface InviteRewardLogListResponse {
  total: number;
  items: InviteRewardLogItem[];
}

export interface AdminInviteRewardSummary {
  total_referrals: number;
  rewarded_referrers: number;
  rewarded_invitees: number;
  reward_grant_count: number;
  source_credits: number;
  reward_credits: number;
  payment_reward_count: number;
  redeem_reward_count: number;
}

export interface AdminInviteRewardUserItem {
  user_id: string;
  username: string;
  email: string;
  invite_code: string;
  total_referrals: number;
  rewarded_invitees: number;
  reward_grant_count: number;
  source_credits: number;
  reward_credits: number;
  last_reward_at?: string | null;
  created_at?: string | null;
}

export interface AdminInviteRewardLogItem {
  id: number;
  referrer_user_id: string;
  referrer_username: string;
  invitee_user_id: string;
  invitee_username: string;
  source_type: "payment" | "redeem" | string;
  source_id: string;
  source_credits: number;
  reward_rate: number;
  reward_credits: number;
  reward_index: number;
  created_at?: string | null;
}

export interface AdminInviteRewardDashboard {
  summary: AdminInviteRewardSummary;
  users: AdminInviteRewardUserItem[];
  recent_logs: AdminInviteRewardLogItem[];
}

export interface AdminInviteRewardDetailReferralItem {
  user_id: string;
  username: string;
  email: string;
  reward_count: number;
  reward_credits: number;
  last_reward_at?: string | null;
  registered_at?: string | null;
}

export interface AdminInviteRewardDetailLogItem {
  id: number;
  invitee_user_id: string;
  invitee_username: string;
  invitee_email: string;
  source_type: "payment" | "redeem" | string;
  source_id: string;
  source_credits: number;
  reward_rate: number;
  reward_credits: number;
  reward_index: number;
  created_at?: string | null;
}

export interface AdminInviteRewardUserDetail {
  user: {
    user_id: string;
    username: string;
    email: string;
    invite_code: string;
    created_at?: string | null;
  };
  summary: Pick<AdminInviteRewardSummary, "total_referrals" | "rewarded_invitees" | "reward_grant_count" | "source_credits" | "reward_credits">;
  referrals: AdminInviteRewardDetailReferralItem[];
  reward_logs: AdminInviteRewardDetailLogItem[];
}

export interface AdminPromoStatsSummary {
  total_referrals: number;
  active_promoters: number;
  total_promo_codes: number;
  used_promo_codes: number;
  whitelisted_users: number;
  reward_credits: number;
  purchase_count: number;
  purchase_credits: number;
  redeem_count: number;
  redeem_credits: number;
}

export interface AdminPromoStatsUserItem {
  user_id: string;
  username: string;
  email: string;
  is_whitelisted: boolean;
  promo_code_count: number;
  used_code_count: number;
  total_referrals: number;
  reward_credits: number;
  purchase_credits: number;
  redeem_credits: number;
  last_referral_at?: string | null;
  created_at?: string | null;
}

export interface AdminPromoStatsReferralItem {
  id: number;
  promoter_user_id: string;
  promoter_username: string;
  invitee_user_id: string;
  invitee_username: string;
  promo_code: string;
  platform_name: string;
  reward_credits: number;
  registered_at?: string | null;
}

export interface AdminPromoStatsDashboard {
  summary: AdminPromoStatsSummary;
  users: AdminPromoStatsUserItem[];
  recent_referrals: AdminPromoStatsReferralItem[];
}

export interface AdminRedeemKey {
  id: number;
  redeem_key: string;
  credit_amount: number;
  batch_no: string;
  status: RedeemKeyStatus;
  is_used: boolean;
  used_at?: string | null;
  used_by_user_id?: string | null;
  used_by_username: string;
  used_by_user_email: string;
  created_by_user_id?: string | null;
  created_by_username: string;
  created_at?: string | null;
}

export interface AdminRedeemKeyBatchResult {
  batch_no: string;
  credit_amount: number;
  count: number;
  items: AdminRedeemKey[];
}

export interface TemplateTag {
  id: number;
  name: string;
  parent_id?: number | null;
  sort_order?: number;
  template_count?: number;
}

export interface CreativeTemplate {
  id: number;
  prompt: string;
  model: string;
  reference_images: string[];
  reference_image_thumbs?: string[];
  num_images: number;
  size: string;
  resolution: string;
  custom_size: string;
  result_image: string;
  result_image_thumb?: string;
  sort_order: number;
  tags: TemplateTag[];
  created_at: string;
}

export interface TemplateListResponse {
  total: number;
  items: CreativeTemplate[];
}

export interface AdminStats {
  total_users: number;
  total_tasks: number;
  total_credit_cost: number;
  active_users: number;
}

export type AdminAnalyticsGranularity = "day" | "week" | "month";

export interface AdminAnalyticsQuery {
  granularity: AdminAnalyticsGranularity;
  start_date?: string;
  end_date?: string;
  user_id?: string;
  source?: TaskSource;
  model?: string;
  mode?: TaskType;
  status?: string;
}

export interface AdminAnalyticsMetric {
  current: number;
  previous: number;
  delta: number;
  delta_pct?: number | null;
}

export interface AdminAnalyticsSummary {
  granularity: AdminAnalyticsGranularity;
  current_range_label: string;
  previous_range_label: string;
  total_users: number;
  tasks_created: AdminAnalyticsMetric;
  success_tasks: AdminAnalyticsMetric;
  failed_tasks: AdminAnalyticsMetric;
  credits_consumed: AdminAnalyticsMetric;
  new_users: AdminAnalyticsMetric;
  active_users: AdminAnalyticsMetric;
}

export interface AdminAnalyticsTimeseriesPoint {
  label: string;
  bucket_start?: string | null;
  bucket_end?: string | null;
  tasks_created: number;
  success_tasks: number;
  failed_tasks: number;
  credits_consumed: number;
  new_users: number;
  active_users: number;
}

export interface AdminAnalyticsTimeseries {
  granularity: AdminAnalyticsGranularity;
  current_range_label: string;
  previous_range_label: string;
  current: AdminAnalyticsTimeseriesPoint[];
  previous: AdminAnalyticsTimeseriesPoint[];
}

export interface AdminAnalyticsBreakdownItem {
  name: string;
  count: number;
  credit_cost: number;
}

export interface AdminDailyReportTestResult {
  sent: boolean;
  report_date: string;
  range_start: string;
  range_end: string;
  revenue_fen: number;
  revenue_yuan: number;
  paid_order_count: number;
  redeem_revenue_yuan: number;
  redeem_used_count: number;
  task_total_count: number;
  task_success_count: number;
  task_failed_count: number;
  credit_consumed: number;
}

export interface AdminAnalyticsBreakdown {
  range_label: string;
  status_breakdown: AdminAnalyticsBreakdownItem[];
  source_breakdown: AdminAnalyticsBreakdownItem[];
  mode_breakdown: AdminAnalyticsBreakdownItem[];
  model_breakdown: AdminAnalyticsBreakdownItem[];
  top_users_by_tasks: AdminAnalyticsBreakdownItem[];
  top_users_by_credit: AdminAnalyticsBreakdownItem[];
}

export interface AdminAnalyticsRedeemRevenueItem {
  credit_amount: number;
  unit_price: number;
  used_count: number;
  total_amount: number;
}

export interface AdminAnalyticsRedeemRevenue {
  range_label: string;
  items: AdminAnalyticsRedeemRevenueItem[];
  total_used_count: number;
  total_amount: number;
}

export interface AdminErrorAnalyticsItem {
  error_category: string;
  error_message: string;
  count: number;
}

export interface AdminErrorAnalytics {
  range_label: string;
  total_failed_tasks: number;
  fallback_task_total: number;
  fallback_success_tasks: number;
  fallback_failed_tasks: number;
  distinct_error_categories: number;
  distinct_error_messages: number;
  items: AdminErrorAnalyticsItem[];
}

export type ErrorTrendGranularity = "1hour" | "3hour" | "6hour";

export interface AdminErrorCategoryTimeseriesSeries {
  error_category: string;
  total_count: number;
}

export interface AdminErrorCategoryTimeseriesPoint {
  label: string;
  bucket_start?: string | null;
  bucket_end?: string | null;
  total_failed_tasks: number;
  categories: Record<string, number>;
}

export interface AdminErrorCategoryTimeseries {
  granularity: ErrorTrendGranularity;
  range_label: string;
  series: AdminErrorCategoryTimeseriesSeries[];
  points: AdminErrorCategoryTimeseriesPoint[];
}

export interface AdminErrorTaskItem {
  task_id: string;
  user_id: string;
  username: string;
  avatar_url: string;
  task_type: TaskType;
  model: string;
  source: TaskSource;
  mode: TaskMode;
  prompt: string;
  status: string;
  error_message: string;
  credit_cost: number;
  credit_refunded: boolean;
  used_fallback_api?: boolean;
  primary_api_config_name?: string;
  primary_http_status?: number | null;
  fallback_api_config_name?: string;
  fallback_status?: "unused" | "success" | "failed" | "partial" | string;
  fallback_error_message?: string;
  created_at?: string | null;
}

export interface AdminErrorTaskList {
  total: number;
  items: AdminErrorTaskItem[];
}

export interface AdminPaymentOrder {
  id: number;
  order_no: string;
  out_trade_no: string;
  alipay_trade_no: string;
  user_id: string;
  username: string;
  user_email: string;
  plan_key: string;
  subject: string;
  amount_fen: number;
  amount_yuan: number;
  credits: number;
  status: "created" | "pending_pay" | "paid" | "credited" | "closed" | "failed";
  trade_status: string;
  buyer_id: string;
  paid_at?: string | null;
  credited_at?: string | null;
  closed_at?: string | null;
  failed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AdminConfig {
  id: number;
  contact_qr_image: string;
  announcement_enabled: boolean;
  announcement_content: string;
  announcement_updated_at?: string | null;
  updated_at: string;
}

export interface ExternalApiSecretConfig {
  id: number;
  key: string;
  tongyi_key: string;
  updated_at?: string | null;
}

export interface CosConfig {
  id: number;
  cos_secret_id: string;
  cos_secret_key: string;
  cos_bucket: string;
  cos_region: string;
  cos_public_base_url: string;
  updated_at?: string | null;
}

export interface AnnouncementConfig {
  announcement_enabled: boolean;
  announcement_content: string;
  announcement_updated_at?: string | null;
}

export type ExternalApiConfigStatus = "enabled" | "disabled";
export type ExternalApiRequestFormat = "json" | "multipart";
export type ExternalApiSceneType = "generate" | "image_edit" | "prompt_reverse" | "prompt_optimize" | "inpaint";

export interface SceneOptionItem {
  label: string;
  value: string;
}

export interface ExternalApiConfig {
  id: number;
  name: string;
  description: string;
  group_name: string;
  request_url: string;
  request_format: ExternalApiRequestFormat;
  headers_json: string;
  payload_json: string;
  response_json: string;
  result_base64_field: string;
  status: ExternalApiConfigStatus;
  created_at: string;
  updated_at?: string;
}

export interface ExternalApiConfigPayload {
  name: string;
  description: string;
  group_name: string;
  request_url: string;
  request_format: ExternalApiRequestFormat;
  headers_json: string;
  payload_json: string;
  response_json: string;
  result_base64_field: string;
  status: ExternalApiConfigStatus;
}

export interface ExternalApiSceneBinding {
  scene_key: string;
  scene_type: ExternalApiSceneType;
  scene_label: string;
  scene_description: string;
  display_name: string;
  subtitle: string;
  sort_order: number;
  hide_aspect_ratio: boolean;
  hide_resolution: boolean;
  hide_custom_size: boolean;
  status: ExternalApiConfigStatus;
  is_builtin: boolean;
  api_config_id?: number | null;
  api_config_name: string;
  api_group_name: string;
  api_status?: ExternalApiConfigStatus | null;
  backup_api_config_id?: number | null;
  backup_api_config_name: string;
  backup_api_group_name: string;
  backup_api_status?: ExternalApiConfigStatus | null;
  credit_cost: number;
  resolution_credit_costs_json: string;
  max_reference_images: number;
  aspect_ratio_options_json: string;
  image_size_options_json: string;
  custom_size_options_json: string;
  resolution_mapping_json: string;
}

export interface ExternalApiSceneBindingCreatePayload {
  scene_key: string;
  scene_type: Extract<ExternalApiSceneType, "generate" | "image_edit">;
  scene_label: string;
  scene_description: string;
  sort_order: number;
  hide_aspect_ratio: boolean;
  hide_resolution: boolean;
  hide_custom_size: boolean;
  api_config_id: number | null;
  backup_api_config_id: number | null;
  display_name: string;
  subtitle: string;
  credit_cost: number;
  max_reference_images: number;
  aspect_ratio_options_json: string;
  image_size_options_json: string;
  custom_size_options_json: string;
  resolution_mapping_json: string;
  resolution_credit_costs_json: string;
}

export interface ExternalApiSceneBindingMetaPayload {
  scene_key: string;
  scene_label: string;
  scene_description: string;
  sort_order: number;
  hide_aspect_ratio: boolean;
  hide_resolution: boolean;
  hide_custom_size: boolean;
  max_reference_images: number;
  aspect_ratio_options_json: string;
  image_size_options_json: string;
  custom_size_options_json: string;
  resolution_mapping_json: string;
  resolution_credit_costs_json: string;
}

export interface ExternalApiConfigTestResult {
  success: boolean;
  request_url: string;
  status_code?: number | null;
  response_preview: string;
}

export interface GenerationModelOption {
  model_key: string;
  model_label: string;
  model_description: string;
  display_name: string;
  subtitle: string;
  sort_order: number;
  hide_aspect_ratio: boolean;
  hide_resolution: boolean;
  hide_custom_size: boolean;
  credit_cost: number;
  resolution_credit_costs: Record<string, number>;
  max_reference_images: number;
  aspect_ratio_options: SceneOptionItem[];
  image_size_options: SceneOptionItem[];
  custom_size_options: SceneOptionItem[];
}

export interface TaskSceneConfig {
  scene_key: string;
  scene_type: ExternalApiSceneType;
  scene_label: string;
  scene_description: string;
  display_name: string;
  subtitle: string;
  sort_order: number;
  hide_aspect_ratio: boolean;
  hide_resolution: boolean;
  hide_custom_size: boolean;
  credit_cost: number;
  resolution_credit_costs: Record<string, number>;
  max_reference_images: number;
  aspect_ratio_options: SceneOptionItem[];
  image_size_options: SceneOptionItem[];
  custom_size_options: SceneOptionItem[];
}

export type UploadPurpose = "ref" | "source" | "mask" | "reverse" | "misc" | "template";

export interface UploadCredential {
  bucket: string;
  region: string;
  key: string;
  url: string;
  tmp_secret_id: string;
  tmp_secret_key: string;
  session_token: string;
  start_time?: number | null;
  expired_time: number;
}

export interface UserPromptCategory {
  id: number;
  name: string;
  sort_order: number;
  prompt_count: number;
  updated_at?: string | null;
}

export interface UserPromptCategoryListResponse {
  items: UserPromptCategory[];
  uncategorized_count: number;
}

export interface UserPrompt {
  id: number;
  category_id?: number | null;
  category_name: string;
  title: string;
  content: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UserPromptListResponse {
  items: UserPrompt[];
  total: number;
}

export interface UserAssetUploadSessionResponse {
  asset: UserAsset;
  quota: UserAssetQuota;
  credential: UploadCredential;
}

export interface UserAssetImportResponse {
  asset: UserAsset;
  quota: UserAssetQuota;
}
