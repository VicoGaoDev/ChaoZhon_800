<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { message } from "ant-design-vue";
import { CloseOutlined, CopyOutlined, DownloadOutlined, LeftOutlined, PictureOutlined, ReloadOutlined, RightOutlined } from "@ant-design/icons-vue";
import dayjs from "dayjs";
import {
  exceedsRealtimeImagePreviewLimit,
  getDisplayImageUrl,
  getPreviewImageUrl,
  LARGE_IMAGE_PREVIEW_NOTICE,
  resolveImageUrl,
  resolvePreviewImageUrl,
} from "@/api/images";
import { withBaseUrl } from "@/lib/assets";
import {
  formatGenerationErrorMessage,
  GENERATION_TASK_FAILURE_MESSAGE,
  getTaskImageFailureMessage,
} from "@/lib/generationErrors";
import type { ImageResult, TaskApiAttempt, UserHistoryCard } from "@/types";

const SIDE_NAV_WIDTH = 76;
const SIDE_NAV_BREAKPOINT = 960;

const props = withDefaults(defineProps<{
  open: boolean;
  item: UserHistoryCard | null;
  loading?: boolean;
  showActions?: boolean;
  showErrorMessage?: boolean;
  showAttemptResponsePreview?: boolean;
  hideCreditCost?: boolean;
  requestPreviewLoading?: boolean;
  hasPrev?: boolean;
  hasNext?: boolean;
  modelOptions?: Array<{ label: string; value: string }>;
  title?: string;
}>(), {
  loading: false,
  showActions: false,
  showErrorMessage: false,
  showAttemptResponsePreview: false,
  hideCreditCost: false,
  requestPreviewLoading: false,
  hasPrev: false,
  hasNext: false,
  modelOptions: () => [],
  title: "任务详情",
});

const emit = defineEmits<{
  "update:open": [value: boolean];
  reedit: [item: UserHistoryCard];
  download: [item: UserHistoryCard];
  "navigate-prev": [];
  "navigate-next": [];
}>();

const viewportWidth = ref(typeof window === "undefined" ? 1280 : window.innerWidth);
const reserveSideNav = computed(() => {
  if (typeof document === "undefined") return false;
  if (viewportWidth.value <= SIDE_NAV_BREAKPOINT) return false;
  return !!document.querySelector(".app-layout-desktop-side-nav .canvas-side-nav");
});
const panelStyle = computed(() => (
  reserveSideNav.value ? { left: `${SIDE_NAV_WIDTH}px` } : { left: "0px" }
));

const previewVisible = ref(false);
const previewSrc = ref("");
const requestPreviewActiveKeys = ref<string[]>([]);
const failedResultAsset = withBaseUrl("failed-result.svg");
const generateTaskCardAsset = withBaseUrl("generate-task-card.svg");
const expiredResultAsset = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="960" viewBox="0 0 960 960">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#fff8ee"/>
      <stop offset="100%" stop-color="#ffe6c8"/>
    </linearGradient>
  </defs>
  <rect width="960" height="960" rx="56" fill="url(#bg)"/>
  <rect x="74" y="74" width="812" height="812" rx="42" fill="none" stroke="#efc784" stroke-dasharray="18 16" stroke-width="10"/>
  <g fill="none" stroke="#d08a24" stroke-linecap="round" stroke-linejoin="round">
    <rect x="282" y="248" width="396" height="286" rx="28" stroke-width="18"/>
    <path d="M326 490l110-108 92 88 72-66 76 86" stroke-width="18"/>
    <circle cx="400" cy="330" r="34" fill="#ffd585" stroke-width="12"/>
  </g>
  <text x="480" y="654" text-anchor="middle" font-size="54" font-weight="700" fill="#8c5a16">原图已过期</text>
  <text x="480" y="726" text-anchor="middle" font-size="34" fill="#a9742e">服务器仅保留 15 天原图</text>
  <text x="480" y="776" text-anchor="middle" font-size="34" fill="#a9742e">请在有效期内查看或下载</text>
</svg>
`)}`;

function firstNonEmptyText(...values: Array<string | undefined | null>) {
  for (const value of values) {
    const text = String(value || "").trim();
    if (text) return text;
  }
  return "";
}

function resolveRawErrorMessage(item: UserHistoryCard, image?: ImageResult | null) {
  const imageError = image?.error_message
    || item.images?.find((img) => img.status === "failed" && img.error_message)?.error_message
    || item.images?.find((img) => img.error_message)?.error_message;
  const attemptError = item.api_attempts?.find((attempt) => attempt.error_message)?.error_message;
  return firstNonEmptyText(item.error_message, imageError, attemptError);
}

function isFailedHistoryItem(item: UserHistoryCard | null | undefined) {
  if (!item) return false;
  return item.status === "failed" || (item.images || []).some((img) => img.status === "failed");
}

const modelLabelMap = computed(() => new Map(props.modelOptions.map((item) => [item.value, item.label])));
const requestPreviewAttempts = computed(() => (
  (props.item?.api_attempts || []).filter((attempt) => attempt.request_preview)
));
const showRequestPreviewSection = computed(() => (
  props.requestPreviewLoading || requestPreviewAttempts.value.length > 0
));
const displayImages = computed((): ImageResult[] => {
  const item = props.item;
  if (!item) return [];
  if (item.images?.length) return item.images;
  if (isFailedHistoryItem(item)) {
    return [{
      id: item.image_id || 0,
      image_url: "",
      status: "failed",
      error_message: item.error_message || "",
    }];
  }
  return [];
});
const displayErrorMessage = computed(() => {
  const item = props.item;
  if (!item || !isFailedHistoryItem(item)) return "";
  const raw = resolveRawErrorMessage(item);
  if (props.showErrorMessage) {
    return formatGenerationErrorMessage(raw, GENERATION_TASK_FAILURE_MESSAGE);
  }
  return getTaskImageFailureMessage(
    item,
    item.images?.find((img) => img.status === "failed") || item.images?.[0],
  );
});

function formatTime(t: string) {
  return t ? dayjs(t).format("YYYY-MM-DD HH:mm:ss") : "-";
}

function statusLabel(status: UserHistoryCard["status"]) {
  const mapping: Record<string, string> = {
    pending: "等待中",
    queued: "排队中",
    processing: "处理中",
    success: "成功",
    failed: "失败",
  };
  return mapping[status] || status;
}

function sourceLabel(source: UserHistoryCard["source"]) {
  if (source === "app") return "App";
  if (source === "api") return "API";
  return "Web";
}

function modeLabel(taskType: UserHistoryCard["task_type"]) {
  if (taskType === "text_generate") return "文生图";
  if (taskType === "image_edit") return "图编辑";
  if (taskType === "inpaint") return "局部重绘";
  if (taskType === "promptReverse") return "提示词反推";
  if (taskType === "promptOptimize") return "提示词优化";
  return taskType;
}

function getModelLabel(model?: string) {
  if (!model) return "-";
  return modelLabelMap.value.get(model) || model;
}

function formatImageSize(size?: number) {
  const bytes = Number(size || 0);
  if (!bytes) return "-";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function getDetailCreditCost(item: UserHistoryCard) {
  if (item.status === "failed" && item.credit_refunded) return 0;
  return Number(item.credit_cost || 0);
}

type DetailMetaChip = {
  text: string;
  kind: "status" | "info";
  status?: UserHistoryCard["status"];
};
type DetailMetaItem = {
  key: string;
  label: string;
  value?: string;
  chips?: DetailMetaChip[];
};

function detailMetaList(item: UserHistoryCard): DetailMetaItem[] {
  const sizeChips: DetailMetaChip[] = [];
  if (item.custom_size) {
    sizeChips.push({ text: item.custom_size, kind: "info" });
  } else {
    if (item.size) sizeChips.push({ text: item.size, kind: "info" });
    if (item.resolution) sizeChips.push({ text: item.resolution, kind: "info" });
  }
  const fileParts = [
    item.image_format || "",
    item.image_size_bytes ? formatImageSize(item.image_size_bytes) : "",
  ].filter(Boolean);
  const metas: Array<DetailMetaItem | null> = [
    { key: "status", label: "状态", chips: [{ text: statusLabel(item.status), kind: "status", status: item.status }] },
    { key: "model", label: "模型", chips: [{ text: getModelLabel(item.model), kind: "info" }] },
    sizeChips.length
      ? { key: "size", label: item.custom_size ? "自定义分辨率" : "宽高比 / 分辨率", chips: sizeChips }
      : null,
    item.task_is_deleted ? { key: "task-deleted", label: "任务状态", value: "已软删除" } : null,
    item.is_soft_deleted
      ? { key: "image-deleted", label: "图片软删除", value: `${item.images.filter((img) => img.is_deleted).length} 张` }
      : null,
    { key: "source-type", label: "来源 / 类型", value: [sourceLabel(item.source), modeLabel(item.task_type)].filter(Boolean).join(" / ") },
    item.style_name ? { key: "style", label: "风格", value: item.style_name } : null,
    fileParts.length ? { key: "file", label: "格式 / 大小", value: fileParts.join(" / ") } : null,
    item.item_type === "task" && item.api_attempts?.length
      ? { key: "fallback", label: "备用接口", value: item.used_fallback_api ? "已调用" : "未调用" }
      : null,
    item.created_at ? { key: "created", label: "创建时间", value: formatTime(item.created_at) } : null,
    item.item_type === "task" && !props.hideCreditCost
      ? { key: "credit", label: "消耗积分", value: String(getDetailCreditCost(item)) }
      : null,
  ];
  return metas.filter((meta): meta is DetailMetaItem => meta != null);
}

function updateViewportWidth() {
  if (typeof window === "undefined") return;
  viewportWidth.value = window.innerWidth;
}

function closeDialog() {
  emit("update:open", false);
}

function navigatePrev() {
  if (!props.hasPrev) return;
  emit("navigate-prev");
}

function navigateNext() {
  if (!props.hasNext) return;
  emit("navigate-next");
}

function handleDetailKeydown(event: KeyboardEvent) {
  if (!props.open) return;
  if (event.key === "Escape") {
    closeDialog();
    return;
  }
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    navigatePrev();
    return;
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    navigateNext();
  }
}

onMounted(() => {
  window.addEventListener("resize", updateViewportWidth);
  window.addEventListener("keydown", handleDetailKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateViewportWidth);
  window.removeEventListener("keydown", handleDetailKeydown);
});

function attemptStatusLabel(status: string) {
  return status === "success" ? "成功" : "失败";
}

function attemptRoleLabel(attempt: TaskApiAttempt) {
  return attempt.is_fallback ? "备用接口" : "主接口";
}

function attemptTargetLabel(attempt: TaskApiAttempt) {
  if (attempt.image_index && attempt.image_index > 0) return `第 ${attempt.image_index} 张结果图`;
  if (attempt.image_id) return `图片 #${attempt.image_id}`;
  return "任务级";
}

function formatDuration(durationMs?: number | null) {
  if (typeof durationMs !== "number" || Number.isNaN(durationMs)) return "-";
  if (durationMs < 1000) return `${durationMs} ms`;
  return `${(durationMs / 1000).toFixed(2)} s`;
}

function isHistoryItemExpired(item: Pick<UserHistoryCard, "created_at" | "status">) {
  if (item.status !== "success") return false;
  if (!item.created_at) return false;
  return dayjs().diff(dayjs(item.created_at), "day", true) >= 15;
}

function getNestedImageSrc(image: Pick<ImageResult, "thumb_url" | "image_url" | "preview_url" | "status">) {
  const displayUrl = getDisplayImageUrl(image);
  if (displayUrl) return displayUrl;
  return image.status === "failed" ? failedResultAsset : "";
}

function getNestedPreviewSrc(image: Pick<ImageResult, "thumb_url" | "image_url" | "preview_url">) {
  return getPreviewImageUrl(image);
}

function shouldShowDetailLargeImagePreviewNotice(item: UserHistoryCard, image: Pick<ImageResult, "status" | "image_size_bytes">) {
  return !isHistoryItemExpired(item) && image.status === "success" && exceedsRealtimeImagePreviewLimit(image.image_size_bytes);
}

function getDetailImageSrc(item: UserHistoryCard, image: Pick<ImageResult, "thumb_url" | "image_url" | "preview_url" | "status" | "image_size_bytes">) {
  if (isHistoryItemExpired(item) && image.status === "success") {
    return expiredResultAsset;
  }
  if (shouldShowDetailLargeImagePreviewNotice(item, image)) {
    return "";
  }
  return getNestedImageSrc(image);
}

function getDetailPreviewSrc(item: UserHistoryCard, image: Pick<ImageResult, "thumb_url" | "image_url" | "preview_url" | "status" | "image_size_bytes">) {
  if (isHistoryItemExpired(item) && image.status === "success") {
    return "";
  }
  if (shouldShowDetailLargeImagePreviewNotice(item, image)) {
    return "";
  }
  return getNestedPreviewSrc(image);
}

function openPreview(url: string) {
  if (!url) return;
  previewSrc.value = url;
  previewVisible.value = true;
}

async function copyPrompt(text?: string) {
  if (!text?.trim()) return;
  try {
    await navigator.clipboard.writeText(text);
    message.success("已复制提示词");
  } catch {
    message.error("复制失败，请重试");
  }
}

function stringifyRequestPayload(payload: unknown) {
  if (payload == null) return "{}";
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
}

function stringifyRequestHeaders(headers?: Record<string, string>) {
  return JSON.stringify(headers || {}, null, 2);
}

function shellQuote(value: string) {
  return `'${String(value || "").replace(/'/g, "'\\''")}'`;
}

function buildRequestCurl(preview: NonNullable<TaskApiAttempt["request_preview"]>) {
  const lines = [`curl ${preview.request_url || ""}`];
  Object.entries(preview.headers || {}).forEach(([name, value]) => {
    lines.push(`  -H ${shellQuote(`${name}: ${value}`)}`);
  });
  lines.push(`  -d ${shellQuote(stringifyRequestPayload(preview.payload))}`);
  return lines.join(" \\\n");
}

async function copyRequestText(text: string, successMessage: string) {
  if (!text.trim()) return;
  try {
    await navigator.clipboard.writeText(text);
    message.success(successMessage);
  } catch {
    message.error("复制失败，请重试");
  }
}

function handleReedit(item: UserHistoryCard) {
  emit("reedit", item);
}

function handleDownload(item: UserHistoryCard) {
  emit("download", item);
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="history-task-detail-overlay"
      :class="{ 'is-side-nav-offset': reserveSideNav }"
      :style="panelStyle"
    >
      <div class="history-task-detail-panel">
        <div class="history-task-detail-header">
          <div class="history-task-detail-title">{{ title }}</div>
          <button type="button" class="history-task-detail-close" aria-label="关闭" @click="closeDialog">
            <CloseOutlined />
          </button>
        </div>
        <div class="history-task-detail-body">
    <div v-if="loading" class="detail-loading">
      <span>正在加载任务详情...</span>
    </div>
    <template v-else-if="item">
      <div :key="item.display_id || item.task_id || item.history_id || item.image_id || item.created_at" class="detail-layout">
        <div class="detail-left">
          <button
            v-if="hasPrev"
            type="button"
            class="detail-nav-btn detail-nav-prev"
            aria-label="上一个任务"
            @click="navigatePrev"
          >
            <LeftOutlined />
          </button>
          <button
            v-if="hasNext"
            type="button"
            class="detail-nav-btn detail-nav-next"
            aria-label="下一个任务"
            @click="navigateNext"
          >
            <RightOutlined />
          </button>
          <div class="detail-section">
            <div v-if="item.mode === 'promptReverse'" class="detail-label">反推原图</div>
            <div v-if="item.mode === 'promptReverse' && item.source_image" class="detail-thumb-row">
              <div
                class="detail-thumb detail-thumb-large"
                @click="!isHistoryItemExpired(item) && openPreview(resolvePreviewImageUrl(item.source_image))"
              >
                <img
                  :src="isHistoryItemExpired(item) ? expiredResultAsset : resolvePreviewImageUrl(item.source_image_thumb || item.source_image)"
                  alt="提示词反推原图"
                  loading="lazy"
                />
              </div>
            </div>
            <div
              v-else
              class="detail-result-grid"
              :class="{
                'is-single': displayImages.length <= 1,
                'is-scrollable': displayImages.length > 4,
              }"
            >
              <div
                v-for="img in displayImages"
                :key="img.id"
                class="detail-result-card"
                :class="{
                  single: displayImages.length <= 1,
                  pending: !getDetailImageSrc(item, img) && img.status !== 'failed' && item.status !== 'failed',
                  failed: img.status === 'failed' || item.status === 'failed',
                }"
                :style="{ '--detail-pending-bg-image': `url('${generateTaskCardAsset}')` }"
                @click="getDetailPreviewSrc(item, img) && openPreview(getDetailPreviewSrc(item, img))"
              >
                <img
                  v-if="getDetailImageSrc(item, img) || img.status === 'failed' || item.status === 'failed'"
                  :src="getDetailImageSrc(item, img) || failedResultAsset"
                  :alt="img.status === 'failed' || item.status === 'failed' ? '生成失败' : '结果图'"
                  :class="{ 'failed-result-image': img.status === 'failed' || item.status === 'failed' }"
                  loading="lazy"
                />
                <div v-else-if="shouldShowDetailLargeImagePreviewNotice(item, img)" class="detail-preview-notice">
                  <span>{{ LARGE_IMAGE_PREVIEW_NOTICE }}</span>
                </div>
                <div v-else class="result-card-placeholder">
                  <span>图片处理中...</span>
                </div>
              </div>
            </div>
            <div v-if="displayErrorMessage" class="detail-inline-error">{{ displayErrorMessage }}</div>
          </div>
        </div>

        <div class="detail-right">
          <div v-if="item.task_is_deleted || item.is_soft_deleted" class="detail-section">
            <div class="detail-alert-list">
              <div v-if="item.task_is_deleted" class="detail-alert detail-alert-danger">
                该任务已被用户软删除，仅在后台历史记录中保留展示。
              </div>
              <div v-if="item.is_soft_deleted" class="detail-alert detail-alert-warning">
                该任务存在已软删图片，当前详情默认仅展示未删除图片。
              </div>
            </div>
          </div>

          <div class="detail-section">
            <div class="detail-meta">
              <div v-for="meta in detailMetaList(item)" :key="meta.key" class="detail-meta-item">
                <span class="detail-meta-label">{{ meta.label }}</span>
                <span class="detail-meta-value">
                  <template v-if="meta.chips?.length">
                    <span
                      v-for="chip in meta.chips"
                      :key="chip.text"
                      class="detail-meta-tag"
                      :class="chip.kind === 'status' ? `is-status-${chip.status}` : 'is-info'"
                    >
                      {{ chip.text }}
                    </span>
                  </template>
                  <template v-else>{{ meta.value }}</template>
                </span>
              </div>
            </div>
          </div>

          <div v-if="showErrorMessage && displayErrorMessage" class="detail-section">
            <div class="detail-error-block">
              <div class="detail-error-label">错误信息</div>
              <div class="detail-error-message">{{ displayErrorMessage }}</div>
            </div>
          </div>

          <div v-if="item.api_attempts?.length" class="detail-section">
            <div class="detail-label">接口调用记录</div>
            <div class="detail-attempt-list">
              <div v-for="attempt in item.api_attempts" :key="`${attempt.id || 'attempt'}-${attempt.image_id || 0}-${attempt.attempt_index}`" class="detail-attempt-card">
                <div class="detail-attempt-header">
                  <span class="detail-attempt-title">{{ attemptTargetLabel(attempt) }}</span>
                  <a-space size="small">
                    <a-tag class="api-tag" :class="attempt.is_fallback ? 'api-tag-group' : 'api-tag-muted'">
                      {{ attemptRoleLabel(attempt) }}
                    </a-tag>
                    <a-tag class="api-tag" :class="attempt.status === 'success' ? 'api-tag-enabled' : 'api-tag-danger'">
                      {{ attemptStatusLabel(attempt.status) }}
                    </a-tag>
                  </a-space>
                </div>
                <div class="detail-attempt-meta">
                  <span>第 {{ attempt.attempt_index }} 次尝试</span>
                  <span>接口：{{ attempt.api_config_name || "-" }}</span>
                  <span>HTTP：{{ typeof attempt.http_status === "number" ? attempt.http_status : "-" }}</span>
                  <span>耗时：{{ formatDuration(attempt.duration_ms) }}</span>
                  <span>第三方响应：{{ formatDuration(attempt.external_http_ms) }}</span>
                  <span>结果下载：{{ formatDuration(attempt.result_download_ms) }}</span>
                  <span>COS上传：{{ formatDuration(attempt.cos_upload_ms) }}</span>
                </div>
                <div v-if="showErrorMessage && attempt.error_message" class="detail-attempt-error">{{ attempt.error_message }}</div>
                <div v-if="showAttemptResponsePreview && attempt.response_preview" class="detail-request-field detail-attempt-response-preview">
                  <div class="detail-request-field-head">
                    <span class="detail-request-label">响应体摘要</span>
                  </div>
                  <pre>{{ attempt.response_preview }}</pre>
                </div>
              </div>
            </div>
          </div>

          <div v-if="showRequestPreviewSection" class="detail-section detail-request-preview-section">
            <div class="detail-label-row detail-request-preview-title-row">
              <div class="detail-label">接口调用参数</div>
              <a-spin v-if="requestPreviewLoading" size="small" />
            </div>
            <div v-if="requestPreviewLoading" class="detail-request-loading">正在加载可复制的接口调用参数...</div>
            <a-collapse
              v-else
              v-model:activeKey="requestPreviewActiveKeys"
              ghost
              class="detail-request-collapse"
            >
              <a-collapse-panel
                v-for="attempt in requestPreviewAttempts"
                :key="String(attempt.id || `${attempt.image_id || 0}-${attempt.attempt_index}`)"
                :header="`${attemptTargetLabel(attempt)} · ${attemptRoleLabel(attempt)} · 第 ${attempt.attempt_index} 次尝试`"
              >
                <template v-if="attempt.request_preview">
                  <div class="detail-request-preview">
                    <div class="detail-request-preview-head">
                      <span>{{ attempt.api_config_name || "绑定接口" }}</span>
                    </div>
                    <div class="detail-request-field">
                      <div class="detail-request-field-head">
                        <div class="detail-request-label">URL</div>
                        <a-tooltip title="复制 URL">
                          <a-button
                            size="small"
                            type="text"
                            class="detail-request-copy-icon"
                            @click="copyRequestText(attempt.request_preview.request_url || '', '已复制 URL')"
                          >
                            <template #icon><CopyOutlined /></template>
                          </a-button>
                        </a-tooltip>
                      </div>
                      <pre>{{ attempt.request_preview.request_url || "-" }}</pre>
                    </div>
                    <div class="detail-request-field">
                      <div class="detail-request-field-head">
                        <div class="detail-request-label">Header</div>
                        <a-tooltip title="复制 Header">
                          <a-button
                            size="small"
                            type="text"
                            class="detail-request-copy-icon"
                            @click="copyRequestText(stringifyRequestHeaders(attempt.request_preview.headers), '已复制 Header')"
                          >
                            <template #icon><CopyOutlined /></template>
                          </a-button>
                        </a-tooltip>
                      </div>
                      <pre>{{ stringifyRequestHeaders(attempt.request_preview.headers) }}</pre>
                    </div>
                    <div class="detail-request-field detail-request-field-scroll">
                      <div class="detail-request-field-head">
                        <div class="detail-request-label">参数 JSON</div>
                        <a-tooltip title="复制参数 JSON">
                          <a-button
                            size="small"
                            type="text"
                            class="detail-request-copy-icon"
                            @click="copyRequestText(stringifyRequestPayload(attempt.request_preview.payload), '已复制参数 JSON')"
                          >
                            <template #icon><CopyOutlined /></template>
                          </a-button>
                        </a-tooltip>
                      </div>
                      <pre>{{ stringifyRequestPayload(attempt.request_preview.payload) }}</pre>
                    </div>
                    <div class="detail-request-field detail-request-field-scroll">
                      <div class="detail-request-field-head">
                        <div class="detail-request-label">curl</div>
                        <a-tooltip title="复制 curl">
                          <a-button
                            size="small"
                            type="text"
                            class="detail-request-copy-icon"
                            @click="copyRequestText(buildRequestCurl(attempt.request_preview), '已复制 curl')"
                          >
                            <template #icon><CopyOutlined /></template>
                          </a-button>
                        </a-tooltip>
                      </div>
                      <pre>{{ buildRequestCurl(attempt.request_preview) }}</pre>
                    </div>
                  </div>
                </template>
              </a-collapse-panel>
            </a-collapse>
          </div>

          <div v-if="item.mode === 'inpaint' && item.source_image" class="detail-section">
            <div class="detail-label">局部重绘原图</div>
            <div class="detail-thumb-row">
              <div class="detail-thumb" @click="!isHistoryItemExpired(item) && openPreview(resolvePreviewImageUrl(item.source_image))">
                <img
                  :src="isHistoryItemExpired(item) ? expiredResultAsset : resolvePreviewImageUrl(item.source_image_thumb || item.source_image)"
                  alt="局部重绘原图"
                  loading="lazy"
                />
              </div>
            </div>
          </div>

          <div v-if="item.reference_images.length" class="detail-section">
            <div class="detail-label">
              <PictureOutlined />
              <span>参考图</span>
            </div>
            <div class="detail-thumb-row">
              <div
                v-for="(ref, index) in item.reference_images"
                :key="index"
                class="detail-thumb"
                @click="openPreview(resolvePreviewImageUrl(ref))"
              >
                <img :src="resolvePreviewImageUrl(item.reference_image_thumbs[index] || ref)" alt="参考图" loading="lazy" />
              </div>
            </div>
          </div>

          <div class="detail-section">
            <div class="detail-label-row">
              <div class="detail-label">提示词</div>
              <a-button type="text" class="detail-copy-btn" @click="copyPrompt(item.prompt)">
                <template #icon><CopyOutlined /></template>
                复制提示词
              </a-button>
            </div>
            <div class="detail-prompt">{{ item.prompt || "-" }}</div>
          </div>
        </div>
        <div v-if="showActions" class="detail-floating-actions">
          <a-tooltip title="重新编辑">
            <a-button type="text" class="ghost-icon-btn detail-action-btn" @click="handleReedit(item)">
              <template #icon><ReloadOutlined /></template>
            </a-button>
          </a-tooltip>
          <a-tooltip title="下载">
            <a-button
              type="text"
              class="ghost-icon-btn detail-action-btn"
              :disabled="isHistoryItemExpired(item) || !item.image_url || typeof item.image_id !== 'number'"
              @click="handleDownload(item)"
            >
              <template #icon><DownloadOutlined /></template>
            </a-button>
          </a-tooltip>
        </div>
      </div>
    </template>
        </div>
      </div>
    </div>
  </Teleport>

  <div v-if="previewVisible" style="display: none">
    <a-image
      :src="previewSrc"
      :preview="{ visible: previewVisible, onVisibleChange: (v: boolean) => (previewVisible = v) }"
    />
  </div>
</template>

<style scoped lang="scss">
.history-task-detail-overlay {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 1200;
  display: flex;
  flex-direction: column;
  background: var(--theme-panel-bg, #fffaf2);
}

.history-task-detail-panel {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.history-task-detail-header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--theme-panel-border);
  background: var(--theme-modal-header-bg, #fff8ec);
}

.history-task-detail-title {
  color: var(--theme-title);
  font-size: 16px;
  font-weight: 700;
}

.history-task-detail-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--theme-title);
  cursor: pointer;
}

.history-task-detail-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

:global(.history-detail-modal .ant-modal) {
  max-width: calc(100vw - 32px);
}

:global(.history-detail-modal .ant-modal-content) {
  max-height: min(88vh, 920px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

:global(.history-detail-modal .ant-modal-body) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.detail-loading {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-secondary);
}

@keyframes history-detail-slide-in {
  from {
    opacity: 0;
    transform: translate3d(22px, 0, 0) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0) scale(1);
  }
}

.detail-section + .detail-section {
  margin-top: 18px;
}

.detail-attempt-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-request-preview-section {
  margin-top: 18px;
}

.detail-request-preview-title-row {
  align-items: center;
}

.detail-request-loading {
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}

.detail-request-collapse {
  margin-top: 10px;
  border-radius: 14px;
  background: var(--theme-panel-bg-soft);
  border: 1px solid var(--theme-panel-border);
}

.detail-request-collapse :deep(.ant-collapse-item) {
  border-bottom: 1px solid var(--theme-panel-border);
}

.detail-request-collapse :deep(.ant-collapse-item:last-child) {
  border-bottom: none;
}

.detail-request-collapse :deep(.ant-collapse-header) {
  font-size: 13px;
  font-weight: 600;
  color: var(--theme-title) !important;
}

.detail-request-collapse :deep(.ant-collapse-content-box) {
  padding-top: 4px !important;
}

.detail-request-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-request-preview-head {
  color: var(--theme-title);
  font-size: 13px;
  font-weight: 700;
}

.detail-request-field + .detail-request-field {
  margin-top: 4px;
}

.detail-request-field-scroll pre {
  height: 220px;
  max-height: 220px;
}

.detail-request-field-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.detail-request-label {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.detail-request-copy-icon {
  color: var(--theme-link) !important;
}

.detail-request-copy-icon:hover {
  color: var(--theme-link-hover, var(--theme-link)) !important;
}

.detail-request-field pre {
  margin: 0;
  padding: 12px 14px;
  overflow: auto;
  border-radius: 12px;
  border: 1px solid var(--theme-panel-border);
  background: var(--theme-panel-bg);
  color: var(--theme-title);
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-attempt-card {
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 12px 14px;
  background: var(--bg-elevated, rgba(255, 255, 255, 0.64));
}

.detail-attempt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.detail-attempt-title {
  font-weight: 600;
  color: var(--text-primary);
}

.detail-attempt-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  color: var(--text-secondary);
  font-size: 13px;
}

.detail-attempt-error {
  margin-top: 8px;
  color: var(--danger-color, #d84f45);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.detail-attempt-response-preview {
  margin-top: 10px;
}

.api-tag-danger {
  color: #b42318;
  background: rgba(217, 45, 32, 0.12);
}

.detail-layout {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.55fr);
  gap: 0;
  align-items: stretch;
  flex: 1 1 auto;
  min-height: 0;
  height: 100%;
  animation: history-detail-slide-in var(--motion-duration-reveal-slower) var(--motion-ease-enter) both;
}

.detail-left,
.detail-right {
  min-width: 0;
  min-height: 0;
}

.detail-left {
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-left: 56px;
  padding-right: 56px;
}

.detail-nav-btn {
  position: absolute;
  top: 50%;
  z-index: 4;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 999px;
  background: rgba(var(--theme-surface-strong-rgb), 0.92);
  color: var(--theme-title);
  box-shadow: 0 10px 24px var(--theme-shadow-soft);
  cursor: pointer;
  transform: translateY(-50%);
}

.detail-nav-prev {
  left: 8px;
}

.detail-nav-next {
  right: 8px;
}

.detail-left > .detail-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.detail-right {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  min-height: 0;
  padding: 16px 16px 44px 20px;
  border-left: 1px solid var(--theme-panel-border);
  scrollbar-width: thin;
}

.detail-alert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-alert {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-size: 13px;
  line-height: 1.7;
}

.detail-alert-danger {
  border-color: rgba(214, 87, 75, 0.22);
  background: rgba(255, 240, 237, 0.96);
  color: #bf5548;
}

.detail-alert-warning {
  border-color: rgba(255, 171, 37, 0.22);
  background: rgba(255, 248, 232, 0.96);
  color: #9b6a1f;
}

.detail-action-btn {
  width: 36px;
  height: 36px;
}

.detail-floating-actions {
  position: absolute;
  right: 0;
  bottom: 0;
  display: flex;
  gap: 6px;
  padding: 0 2px 2px 0;
}

.detail-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
}

.detail-section > .detail-label {
  margin-bottom: 10px;
}

.detail-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.detail-copy-btn {
  height: 30px;
  padding-inline: 10px;
  border-radius: 10px;
  color: var(--theme-link) !important;
}

.detail-prompt {
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--theme-panel-bg-soft);
  border: 1px solid var(--theme-panel-border);
  color: var(--theme-title);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 210px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.detail-error-block {
  margin-top: 0;
}

.detail-inline-error {
  flex-shrink: 0;
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(207, 63, 54, 0.18);
  background: rgba(255, 242, 239, 0.96);
  color: #cf3f36;
  font-size: 13px;
  line-height: 1.6;
  font-weight: 600;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-error-label {
  margin-bottom: 8px;
  color: #b85d47;
  font-size: 13px;
  font-weight: 700;
}

.detail-error-message {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(207, 63, 54, 0.16);
  background: rgba(255, 242, 239, 0.92);
  color: #b85d47;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-thumb-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.detail-thumb {
  width: 84px;
  height: 84px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);
  cursor: pointer;
  transition:
    transform var(--motion-duration-base) var(--motion-ease-soft),
    box-shadow var(--motion-duration-base) var(--motion-ease-soft),
    border-color var(--motion-duration-base) var(--motion-ease-soft);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  &:hover {
    transform: translateY(-2px);
    border-color: var(--theme-border-strong);
    box-shadow: 0 16px 24px var(--theme-shadow-soft);
  }
}

.detail-thumb-large {
  width: min(100%, 520px);
  height: auto;
  aspect-ratio: 1 / 1;
}

.detail-result-grid {
  --detail-result-gap: 12px;
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-rows: calc((100% - var(--detail-result-gap)) / 2);
  gap: var(--detail-result-gap);
  align-content: start;
  overflow-x: hidden;
  overflow-y: hidden;

  &.is-single {
    grid-template-columns: 1fr;
    grid-auto-rows: minmax(0, 1fr);
    align-content: stretch;
    overflow: hidden;
  }

  &.is-scrollable {
    overflow-y: auto;
    padding-right: 2px;
  }
}

.detail-result-card {
  min-width: 0;
  min-height: 0;
  height: 100%;
  box-sizing: border-box;
  border-radius: 0;
  overflow: hidden;
  border: 0;
  background: transparent;
  position: relative;
  cursor: pointer;
  transition:
    transform var(--motion-duration-base) var(--motion-ease-soft),
    box-shadow var(--motion-duration-base) var(--motion-ease-soft),
    border-color var(--motion-duration-base) var(--motion-ease-soft);

  img,
  .result-card-placeholder {
    width: 100%;
    height: 100%;
  }

  img {
    object-fit: contain;
    display: block;
    background: var(--theme-panel-bg);
  }

  &:not(.single) {
    border: 1px solid var(--theme-panel-border);
    border-radius: 10px;
    background: var(--theme-panel-bg);
  }

  &.pending {
    cursor: default;
    background:
      linear-gradient(180deg, rgba(255, 252, 246, 0.24), rgba(255, 248, 238, 0.34)),
      linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg));
  }

  &.pending::before {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--detail-pending-bg-image) center / cover no-repeat;
    opacity: 0.5;
    pointer-events: none;
  }

  &:not(.pending):hover {
    transform: translateY(-3px);
    border-color: var(--theme-border-strong);
    box-shadow: 0 16px 28px var(--theme-shadow-medium);
  }

  &.single:not(.pending):hover {
    transform: none;
    box-shadow: none;
  }

  &.failed img {
    object-fit: contain;
    padding: 18px;
    background: var(--theme-panel-bg);
  }
}

.result-card-placeholder {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  color: var(--theme-text-primary);
  text-align: center;
  font-size: 15px;
  line-height: 1.6;
  font-weight: 600;
  background: linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg));

  span {
    max-width: min(100%, 240px);
    padding: 10px 14px;
    border-radius: 12px;
    background: rgba(var(--theme-surface-strong-rgb), 0.84);
    box-shadow: 0 8px 18px rgba(76, 52, 26, 0.1);
  }
}

.detail-preview-notice {
  position: relative;
  z-index: 3;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #6f4d1f;
  text-align: center;
  font-size: 15px;
  line-height: 1.75;
  font-weight: 600;
  background:
    linear-gradient(180deg, rgba(255, 249, 241, 0.94), rgba(255, 245, 232, 0.98)),
    linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg));

  span {
    max-width: min(100%, 320px);
    padding: 12px 16px;
    border-radius: 14px;
    background: rgba(255, 252, 247, 0.98);
    border: 1px solid rgba(201, 160, 102, 0.22);
    box-shadow: 0 12px 28px rgba(76, 52, 26, 0.14);
  }
}

.failed-result-image {
  object-fit: contain !important;
  padding: 28px;
  background: linear-gradient(180deg, #fff2ef, #ffdcd5);
  opacity: 0.96;
}

.detail-failure-message {
  position: absolute;
  z-index: 4;
  left: 14px;
  right: 14px;
  bottom: 14px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 245, 244, 0.96);
  color: #cf3f36;
  font-size: 13px;
  line-height: 1.55;
  font-weight: 600;
  box-shadow: 0 10px 24px rgba(207, 63, 54, 0.12);
  pointer-events: none;
  white-space: pre-wrap;
  word-break: break-word;
}

.detail-meta {
  display: flex;
  flex-direction: column;
  padding: 2px 16px;
  border-radius: 12px;
  background: var(--theme-panel-bg-soft);
  border: 1px solid var(--theme-panel-border);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.detail-meta-item {
  display: grid;
  grid-template-columns: 8.5em minmax(0, 1fr);
  align-items: center;
  column-gap: 20px;
  min-height: 28px;
  padding: 3px 0;
}

.detail-meta-label {
  color: var(--theme-title);
  font-weight: 700;
}

.detail-meta-value {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  color: var(--theme-title);
}

.detail-meta-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
}

.detail-meta-tag.is-status-success {
  color: #067647;
  background: rgba(18, 183, 106, 0.14);
}

.detail-meta-tag.is-status-failed {
  color: #b42318;
  background: rgba(217, 45, 32, 0.12);
}

.detail-meta-tag.is-status-processing {
  color: #b54708;
  background: rgba(247, 144, 9, 0.16);
}

.detail-meta-tag.is-status-queued,
.detail-meta-tag.is-status-pending {
  color: #175cd3;
  background: rgba(46, 144, 250, 0.14);
}

.detail-meta-tag.is-info {
  color: var(--theme-title);
  background: rgba(46, 144, 250, 0.14);
}

@media (prefers-reduced-motion: reduce) {
  .detail-layout,
  .detail-thumb,
  .detail-result-card {
    animation: none !important;
    transition: none !important;
  }
}

@media (max-width: 900px) {
  .detail-layout {
    grid-template-columns: 1fr;
    height: auto;
  }

  .detail-floating-actions {
    position: static;
    justify-content: flex-end;
    margin-top: 14px;
    padding: 0;
  }

  .detail-left,
  .detail-right {
    overflow: visible;
  }
}
</style>
