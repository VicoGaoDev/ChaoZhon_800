<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, h, watch } from "vue";
import { message, Modal } from "ant-design-vue";
import dayjs from "dayjs";
import {
  CheckSquareOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  EyeOutlined,
  LoadingOutlined,
  MessageOutlined,
  PictureOutlined,
  PushpinOutlined,
  ReloadOutlined,
} from "@ant-design/icons-vue";
import { useRoute, useRouter } from "vue-router";
import { getAdminHistoryCards, getAdminHistoryDetail, listUsers } from "@/api/admin";
import { getGenerationModels, getTaskScenes } from "@/api/config";
import { deleteHistoryTask, fetchHistory, toggleHistoryPin } from "@/api/history";
import {
  exceedsRealtimeImagePreviewLimit,
  getDisplayImageUrl,
  getDownloadUrl,
  getPreviewImageUrl,
  LARGE_IMAGE_PREVIEW_NOTICE,
  resolveImageUrl,
  resolvePreviewImageUrl,
} from "@/api/images";
import { deletePromptHistory, deletePromptOptimizeTask } from "@/api/auth";
import AdminUserInfoDialog from "@/components/admin/AdminUserInfoDialog.vue";
import FeedbackDialog from "@/components/feedback/FeedbackDialog.vue";
import HistoryDetailDialog from "@/components/history/HistoryDetailDialog.vue";
import TemplateEditorDialog from "@/components/templates/TemplateEditorDialog.vue";
import { withBaseUrl } from "@/lib/assets";
import { useAuthStore } from "@/stores/auth";
import {
  HISTORY_GRID_COLUMN_COUNT_KEY,
  readStoredGridColumnCount,
  writeStoredGridColumnCount,
} from "@/lib/gridColumnPreference";
import type { AdminUser, GenerationModelOption, TaskSceneConfig, TaskSource, TaskType, UserHistoryCard } from "@/types";

const props = withDefaults(defineProps<{
  adminUserTasks?: boolean;
}>(), {
  adminUserTasks: false,
});
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const items = ref<UserHistoryCard[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const loading = ref(false);
const loadingMore = ref(false);
const HISTORY_GRID_COLUMN_OPTIONS = [5, 6, 7, 8] as const;
type HistoryGridColumnOption = typeof HISTORY_GRID_COLUMN_OPTIONS[number];
const DEFAULT_HISTORY_GRID_COLUMN_COUNT: HistoryGridColumnOption = 6;
const gridColumnCount = ref<HistoryGridColumnOption>(
  readStoredGridColumnCount(
    HISTORY_GRID_COLUMN_COUNT_KEY,
    HISTORY_GRID_COLUMN_OPTIONS,
    DEFAULT_HISTORY_GRID_COLUMN_COUNT,
  ),
);
const typeFilter = ref<TaskType | undefined>(undefined);
const sourceFilter = ref<TaskSource | undefined>(undefined);
const modelFilter = ref<string | undefined>(undefined);
const statusFilter = ref<"pending" | "processing" | "success" | "failed" | undefined>(undefined);
const fallbackFilter = ref<"used" | undefined>(undefined);
const userFilter = ref<string | undefined>(
  typeof route.query.user === "string" ? route.query.user : undefined,
);
const promptFilter = ref("");
const dateRangeFilter = ref<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
const users = ref<AdminUser[]>([]);
const generationModels = ref<GenerationModelOption[]>([]);
const taskScenes = ref<TaskSceneConfig[]>([]);
const detailOpen = ref(false);
const detailLoading = ref(false);
const failedResultAsset = withBaseUrl("failed-result.svg");
const generateEmptyStateAsset = withBaseUrl("generate-task-card.svg");
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
const detailItem = ref<UserHistoryCard | null>(null);
const selectedImageIds = ref<number[]>([]);
const batchMode = ref(false);
const loadMoreAnchor = ref<HTMLElement | null>(null);
const HISTORY_POLL_INTERVAL_MS = 10000;
let historyPollTimer: number | null = null;
let filterDebounceTimer: number | null = null;
let loadMoreObserver: IntersectionObserver | null = null;
let activeDetailRequestKey = "";

const previewVisible = ref(false);
const previewSrc = ref("");
const feedbackDialogOpen = ref(false);
const feedbackTarget = ref<UserHistoryCard | null>(null);
const pinningKeys = ref<string[]>([]);
const templateDialogRef = ref<InstanceType<typeof TemplateEditorDialog> | null>(null);
const isAdminHistoryView = computed(() => props.adminUserTasks && auth.isAdmin);
const userInfoDialogOpen = ref(false);
const selectedUserInfo = ref<AdminUser | null>(null);

const modelOptions = computed(() => {
  const optionMap = new Map<string, string>();
  generationModels.value.forEach((item) => {
    optionMap.set(item.model_key, item.model_label);
  });
  taskScenes.value
    .filter((item) => item.scene_type === "image_edit")
    .forEach((item) => {
      optionMap.set(item.scene_key, item.display_name || item.scene_label);
    });
  optionMap.set("inpaint", "局部重绘");
  optionMap.set("提示词反推", "提示词反推");
  return Array.from(optionMap.entries()).map(([value, label]) => ({ value, label }));
});
const modelLabelMap = computed(() => new Map(modelOptions.value.map((item) => [item.value, item.label])));

const activeFilterCount = computed(() => {
  let count = 0;
  if (typeFilter.value) count += 1;
  if (sourceFilter.value) count += 1;
  if (modelFilter.value) count += 1;
  if (statusFilter.value) count += 1;
  if (isAdminHistoryView.value && fallbackFilter.value) count += 1;
  if (isAdminHistoryView.value && userFilter.value) count += 1;
  if (promptFilter.value.trim()) count += 1;
  if (dateRangeFilter.value) count += 1;
  return count;
});
const hasMoreHistory = computed(() => items.value.length < total.value);
const historyGridStyle = computed(() => ({
  "--history-grid-columns": String(gridColumnCount.value),
}));

watch(gridColumnCount, (count) => {
  writeStoredGridColumnCount(HISTORY_GRID_COLUMN_COUNT_KEY, count);
});

const currentPageIds = computed(() => (
  items.value
    .map((item) => item.image_id)
    .filter((id): id is number => typeof id === "number")
));
const selectedItems = computed(() => (
  items.value.filter((item) => typeof item.image_id === "number" && selectedImageIds.value.includes(item.image_id))
));
const selectedCount = computed(() => selectedItems.value.length);
const selectableCount = computed(() => items.value.length);
const downloadableSelectedItems = computed(() => selectedItems.value.filter((item) => !!item.image_url));
const allVisibleSelected = computed(() => (
  !!items.value.length
  && items.value
    .filter((item) => typeof item.image_id === "number")
    .every((item) => selectedImageIds.value.includes(item.image_id as number))
));

function hasRunningTasks(list: UserHistoryCard[]) {
  return list.some((item) => item.status === "pending" || item.status === "queued" || item.status === "processing");
}

function stopHistoryPolling() {
  if (historyPollTimer) {
    clearInterval(historyPollTimer);
    historyPollTimer = null;
  }
}

function syncHistoryPolling() {
  if (!hasRunningTasks(items.value)) {
    stopHistoryPolling();
    return;
  }
  if (historyPollTimer) return;
  historyPollTimer = window.setInterval(() => {
    if (loading.value || loadingMore.value) return;
    loadHistory(true);
  }, HISTORY_POLL_INTERVAL_MS);
}

function getHistoryQuery() {
  return {
    respect_pins: false,
    include_prompt_reverse: !isAdminHistoryView.value,
    mode: typeFilter.value,
    source: sourceFilter.value,
    model: modelFilter.value,
    user_id: isAdminHistoryView.value ? userFilter.value : undefined,
    prompt: promptFilter.value,
    status: statusFilter.value,
    used_fallback_api: isAdminHistoryView.value && fallbackFilter.value === "used" ? true : undefined,
    start_date: dateRangeFilter.value?.[0].startOf("day").toISOString(),
    end_date: dateRangeFilter.value?.[1].endOf("day").toISOString(),
  };
}

function syncSelection(list: UserHistoryCard[]) {
  selectedImageIds.value = selectedImageIds.value.filter((id) => list.some((item) => item.image_id === id));
}

function syncDetail(list: UserHistoryCard[]) {
  if (!detailItem.value) return;
  const refreshedDetail = list.find((item) => item.image_id === detailItem.value?.image_id);
  if (refreshedDetail) detailItem.value = refreshedDetail;
}

async function fetchHistoryPage(targetPage: number) {
  if (isAdminHistoryView.value) {
    return getAdminHistoryCards(targetPage, pageSize.value, getHistoryQuery());
  }
  return fetchHistory(targetPage, pageSize.value, getHistoryQuery());
}

async function loadHistory(silent = false) {
  loading.value = true;
  try {
    const targetPages = Math.max(1, page.value);
    const results = await Promise.all(
      Array.from({ length: targetPages }, (_, index) => fetchHistoryPage(index + 1))
    );
    const mergedItems = results.flatMap((result) => result.items);
    items.value = mergedItems;
    total.value = results[0]?.total || 0;
    syncSelection(mergedItems);
    syncDetail(mergedItems);
    syncHistoryPolling();
  } catch {
    if (!silent) message.error("获取历史记录失败");
  } finally {
    loading.value = false;
  }
}

async function loadNextPage() {
  if (loading.value || loadingMore.value || !hasMoreHistory.value) return;
  loadingMore.value = true;
  try {
    const nextPage = page.value + 1;
    const res = await fetchHistoryPage(nextPage);
    items.value = [...items.value, ...res.items];
    total.value = res.total;
    page.value = nextPage;
    syncHistoryPolling();
  } catch {
    message.error("加载更多历史记录失败");
  } finally {
    loadingMore.value = false;
  }
}

function setupLoadMoreObserver(target: HTMLElement | null) {
  loadMoreObserver?.disconnect();
  loadMoreObserver = null;
  if (!target) return;

  loadMoreObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) void loadNextPage();
    },
    { root: null, rootMargin: "0px 0px 260px 0px", threshold: 0.01 }
  );
  loadMoreObserver.observe(target);
}

async function loadModels() {
  try {
    const [models, scenes] = await Promise.all([getGenerationModels(), getTaskScenes()]);
    generationModels.value = models;
    taskScenes.value = scenes;
  } catch {
    generationModels.value = [];
    taskScenes.value = [];
  }
}

async function loadUsers() {
  if (!isAdminHistoryView.value) return;
  try {
    users.value = (await listUsers()).filter((item) => !item.is_whitelisted);
  } catch {
    users.value = [];
  }
}

onMounted(loadHistory);
onMounted(loadModels);
onMounted(loadUsers);
onBeforeUnmount(() => {
  stopHistoryPolling();
  if (filterDebounceTimer) {
    clearTimeout(filterDebounceTimer);
    filterDebounceTimer = null;
  }
  loadMoreObserver?.disconnect();
  loadMoreObserver = null;
});

watch(loadMoreAnchor, (target) => {
  setupLoadMoreObserver(target);
});

function modeLabel(taskType: UserHistoryCard["task_type"]) {
  if (taskType === "text_generate") return "文生图";
  if (taskType === "image_edit") return "图编辑";
  if (taskType === "inpaint") return "局部重绘";
  if (taskType === "promptReverse") return "提示词反推";
  if (taskType === "promptOptimize") return "提示词优化";
  return taskType;
}

function isPromptHistoryMode(mode: UserHistoryCard["mode"]) {
  return mode === "promptReverse" || mode === "promptOptimize";
}

function isPromptHistoryItem(item: UserHistoryCard) {
  return item.item_type === "prompt_history" || item.item_type === "prompt_optimize_task";
}

function getModelLabel(model?: string) {
  if (!model) return "";
  return modelLabelMap.value.get(model) || model;
}

function formatRunTime(seconds?: number | null) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "";
  const normalizedSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(normalizedSeconds / 60);
  const remainSeconds = normalizedSeconds % 60;
  if (minutes <= 0) return `${remainSeconds}秒`;
  return `${minutes}分${remainSeconds}秒`;
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

function formatTime(value?: string | null) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "-";
}

function isHistoryItemPending(status: UserHistoryCard["status"]) {
  return status === "pending" || status === "queued" || status === "processing";
}

function isHistoryItemExpired(item: Pick<UserHistoryCard, "created_at" | "status">) {
  if (item.status !== "success") return false;
  if (!item.created_at) return false;
  return dayjs().diff(dayjs(item.created_at), "day", true) >= 15;
}

function resetFilters() {
  typeFilter.value = undefined;
  sourceFilter.value = undefined;
  modelFilter.value = undefined;
  statusFilter.value = undefined;
  fallbackFilter.value = undefined;
  userFilter.value = undefined;
  promptFilter.value = "";
  dateRangeFilter.value = null;
}

watch(
  [
    typeFilter,
    sourceFilter,
    modelFilter,
    statusFilter,
    fallbackFilter,
    userFilter,
    promptFilter,
    dateRangeFilter,
  ],
  () => {
    if (filterDebounceTimer) clearTimeout(filterDebounceTimer);
    filterDebounceTimer = window.setTimeout(() => {
      page.value = 1;
      loadHistory(true);
    }, 250);
  }
);

function openPreview(url: string) {
  if (!url) return;
  previewSrc.value = url;
  previewVisible.value = true;
}

function getHistoryImageSrc(image: Pick<UserHistoryCard, "thumb_url" | "image_url" | "preview_url" | "status">) {
  const displayUrl = getDisplayImageUrl(image);
  if (displayUrl) return displayUrl;
  return image.status === "failed" ? failedResultAsset : "";
}

function getHistoryCardMedia(item: UserHistoryCard) {
  if (isHistoryItemExpired(item)) {
    return expiredResultAsset;
  }
  if (isPromptHistoryMode(item.mode)) {
    return resolvePreviewImageUrl(item.source_image_thumb || item.source_image);
  }
  if (shouldShowHistoryLargeImagePreviewNotice(item)) {
    return "";
  }
  return getHistoryImageSrc(item);
}

function shouldShowHistoryLargeImagePreviewNotice(item: UserHistoryCard) {
  return !isPromptHistoryMode(item.mode) && item.status === "success" && exceedsRealtimeImagePreviewLimit(item.image_size_bytes);
}

function getHistoryCardPreview(item: UserHistoryCard) {
  if (isHistoryItemExpired(item)) {
    return "";
  }
  if (isPromptHistoryMode(item.mode)) {
    return resolvePreviewImageUrl(item.source_image);
  }
  return getHistoryPreviewSrc(item);
}

function getHistoryPreviewSrc(image: Pick<UserHistoryCard, "thumb_url" | "image_url" | "preview_url">) {
  return getPreviewImageUrl(image);
}

async function openDetail(item: UserHistoryCard) {
  detailItem.value = item;
  detailOpen.value = true;
  if (!isAdminHistoryView.value) return;
  detailLoading.value = true;
  const requestKey = `${item.item_type}:${item.task_id || item.history_id || item.display_id || item.created_at}`;
  activeDetailRequestKey = requestKey;
  try {
    const detail = await getAdminHistoryDetail({
      item_type: item.item_type,
      task_id: item.task_id,
      history_id: item.history_id || undefined,
    });
    if (activeDetailRequestKey !== requestKey) return;
    detailItem.value = detail;
  } catch {
    if (activeDetailRequestKey !== requestKey) return;
    message.error("获取任务详情失败");
  } finally {
    if (activeDetailRequestKey === requestKey) {
      detailLoading.value = false;
    }
  }
}

function findAdminUser(userId?: string) {
  if (!userId) return null;
  return users.value.find((user) => user.id === userId) || null;
}

function openUserInfoDialog(item: UserHistoryCard) {
  if (!isAdminHistoryView.value || !item.user_id) return;
  const matchedUser = findAdminUser(item.user_id);
  selectedUserInfo.value = matchedUser || {
    id: item.user_id,
    username: item.username || "未知用户",
    avatar_url: item.avatar_url || "",
    role: "user",
    status: "",
    is_whitelisted: false,
    credits: 0,
    consumed_credits: 0,
    created_at: "",
  };
  userInfoDialogOpen.value = true;
}

function handleViewUserData(user: AdminUser) {
  userFilter.value = user.id;
  page.value = 1;
  userInfoDialogOpen.value = false;
  void loadHistory(true);
}

function openFeedbackDialog(item: UserHistoryCard) {
  if (isAdminHistoryView.value) {
    message.warning("管理员查看全量历史时暂不支持代用户反馈");
    return;
  }
  if (!item.task_id) {
    message.warning("当前记录暂不支持反馈");
    return;
  }
  feedbackTarget.value = item;
  feedbackDialogOpen.value = true;
}

function canHistoryViewOriginal(item: UserHistoryCard) {
  return Boolean(getHistoryCardPreview(item));
}

function canEditHistoryImage(item: UserHistoryCard) {
  return item.status !== "failed" && !isHistoryItemExpired(item);
}

function canCreateTemplateFromHistory(item: UserHistoryCard) {
  return auth.isSuperAdmin
    && item.status === "success"
    && !isPromptHistoryMode(item.mode)
    && !!item.task_id
    && typeof item.image_id === "number"
    && !isHistoryItemExpired(item)
    && !!item.image_url;
}

function handleCreateTemplateFromHistory(item: UserHistoryCard) {
  if (!item.task_id || typeof item.image_id !== "number") return;
  const draft = {
    task_id: item.task_id,
    image_id: item.image_id,
    prompt: item.prompt || "",
    model: item.model,
    reference_images: [...(item.reference_images || [])],
    result_image: item.image_url,
    size: item.size || "9:16",
    resolution: item.resolution || "2K",
    custom_size: item.custom_size || "",
  };
  templateDialogRef.value?.openFromTask(draft);
}

function handleViewOriginal(item: UserHistoryCard) {
  const url = getHistoryCardPreview(item);
  if (!url) return;
  openPreview(url);
}

function isSelected(imageId: number) {
  return selectedImageIds.value.includes(imageId);
}

function toggleSelect(imageId: number, checked: boolean) {
  if (checked) {
    if (!selectedImageIds.value.includes(imageId)) selectedImageIds.value = [...selectedImageIds.value, imageId];
    return;
  }
  selectedImageIds.value = selectedImageIds.value.filter((id) => id !== imageId);
}

function handleSelectChange(imageId: number, event: { target: { checked: boolean } }) {
  toggleSelect(imageId, event.target.checked);
}

function selectAllVisible() {
  selectedImageIds.value = [...currentPageIds.value];
}

function invertVisibleSelection() {
  selectedImageIds.value = currentPageIds.value.filter((id) => !selectedImageIds.value.includes(id));
}

function getHistoryItemKey(item: UserHistoryCard) {
  if (typeof item.image_id === "number") return item.image_id;
  if (item.task_id) return item.task_id;
  if (item.history_id) return `${item.item_type}-${item.history_id}`;
  return `${item.mode}-${item.created_at}`;
}

function getHistoryPinPayload(item: UserHistoryCard) {
  if (item.item_type === "task") {
    if (typeof item.image_id !== "number") return null;
    return {
      item_type: "task" as const,
      image_id: item.image_id,
    };
  }
  if (!item.history_id) return null;
  return {
    item_type: item.item_type,
    history_id: item.history_id,
  };
}

async function deletePromptLikeHistoryItem(item: UserHistoryCard) {
  if (!item.history_id) return;
  if (item.item_type === "prompt_optimize_task") {
    await deletePromptOptimizeTask(item.history_id);
    return;
  }
  await deletePromptHistory(item.history_id);
}

function isPinning(item: UserHistoryCard) {
  return pinningKeys.value.includes(String(getHistoryItemKey(item)));
}

function canPinHistoryItem(item: UserHistoryCard) {
  return !isAdminHistoryView.value && item.status !== "failed";
}

function clearSelection() {
  selectedImageIds.value = [];
}

function toggleBatchMode() {
  batchMode.value = !batchMode.value;
  if (!batchMode.value) clearSelection();
}

function download(imageId: number, imageUrl: string) {
  const a = document.createElement("a");
  a.href = getDownloadUrl(imageId, imageUrl);
  a.download = `banana_${imageId}.png`;
  a.click();
}

function handleDetailDownload(item: UserHistoryCard) {
  if (typeof item.image_id !== "number" || !item.image_url) return;
  download(item.image_id, item.image_url);
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function getDownloadFilename(imageId: number, imageUrl?: string) {
  const cleanPath = (imageUrl || "").split("?")[0] || "";
  const suffix = cleanPath.includes(".") ? cleanPath.slice(cleanPath.lastIndexOf(".")) : ".png";
  return `banana_${imageId}${suffix || ".png"}`;
}

async function downloadBlob(imageId: number, imageUrl: string) {
  const url = getDownloadUrl(imageId, imageUrl);
  const headers: Record<string, string> = {};
  const token = localStorage.getItem("token");
  if (token && !/^https?:\/\//.test(url)) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(url, { headers });
  if (!response.ok) throw new Error("download_failed");

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = getDownloadFilename(imageId, imageUrl);
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

async function handleDelete(item: UserHistoryCard) {
  if (isAdminHistoryView.value) {
    message.warning("管理员查看全量历史时暂不支持删除用户历史");
    return;
  }
  Modal.confirm({
    title: isPromptHistoryItem(item) ? `确认删除这条${modeLabel(item.task_type)}记录？` : "确认删除这个任务？",
    content: isPromptHistoryItem(item)
      ? `删除后将移除这条${modeLabel(item.task_type)}历史记录。`
      : "删除后会移除该任务及其结果图，AI 生图页面和历史记录中的对应任务也会一并删除。",
    centered: true,
    async onOk() {
      if (isPromptHistoryItem(item) && item.history_id) {
        await deletePromptLikeHistoryItem(item);
      } else {
        if (!item.task_id) return;
        await deleteHistoryTask(item.task_id);
      }
      message.success("删除成功");
      if (typeof item.image_id === "number") {
        selectedImageIds.value = selectedImageIds.value.filter((id) => id !== item.image_id);
      }
      if (items.value.length === 1 && page.value > 1) page.value -= 1;
      if (detailItem.value?.image_id === item.image_id) detailOpen.value = false;
      await loadHistory();
    },
  });
}

async function handleTogglePin(item: UserHistoryCard) {
  if (!canPinHistoryItem(item)) {
    message.warning("失败任务不支持置顶");
    return;
  }
  const payload = getHistoryPinPayload(item);
  if (!payload) {
    message.warning("当前记录暂不支持置顶");
    return;
  }

  const pinKey = String(getHistoryItemKey(item));
  if (pinningKeys.value.includes(pinKey)) return;

  pinningKeys.value = [...pinningKeys.value, pinKey];
  try {
    const result = await toggleHistoryPin(payload);
    message.success(result.is_pinned ? "已置顶到顶部" : "已取消置顶");
    await loadHistory(true);
  } catch {
    message.error(item.is_pinned ? "取消置顶失败" : "置顶失败，请重试");
  } finally {
    pinningKeys.value = pinningKeys.value.filter((key) => key !== pinKey);
  }
}

async function handleBatchDownload() {
  if (!selectedCount.value) {
    message.warning("请先选择需要下载的记录");
    return;
  }
  if (!downloadableSelectedItems.value.length) {
    message.warning("选中项中没有可下载的原图");
    return;
  }

  let successCount = 0;
  for (const item of downloadableSelectedItems.value) {
    try {
      if (typeof item.image_id !== "number") continue;
      await downloadBlob(item.image_id, item.image_url);
      successCount += 1;
      await wait(180);
    } catch {
      // continue downloading remaining items
    }
  }

  if (!successCount) {
    message.error("批量下载失败，请重试");
    return;
  }
  if (successCount < downloadableSelectedItems.value.length) {
    message.warning(`已下载 ${successCount} 张，部分图片下载失败`);
    return;
  }
  message.success(`已开始下载 ${successCount} 张图片`);
}

function getBatchDeleteTargets() {
  const promptHistoryIds = new Set<number>();
  const promptOptimizeTaskIds = new Set<number>();
  const taskIds = new Set<string>();
  selectedItems.value.forEach((item) => {
    if (item.item_type === "prompt_history" && item.history_id) {
      promptHistoryIds.add(item.history_id);
      return;
    }
    if (item.item_type === "prompt_optimize_task" && item.history_id) {
      promptOptimizeTaskIds.add(item.history_id);
      return;
    }
    if (item.task_id) taskIds.add(item.task_id);
  });
  return {
    promptHistoryIds: Array.from(promptHistoryIds),
    promptOptimizeTaskIds: Array.from(promptOptimizeTaskIds),
    taskIds: Array.from(taskIds),
  };
}

async function deleteSelectedItems() {
  const selectedBeforeDelete = selectedItems.value.slice();
  const { promptHistoryIds, promptOptimizeTaskIds, taskIds } = getBatchDeleteTargets();
  const operations = [
    ...promptHistoryIds.map((id) => ({ key: `prompt:${id}`, run: () => deletePromptHistory(id) })),
    ...promptOptimizeTaskIds.map((id) => ({ key: `prompt-optimize:${id}`, run: () => deletePromptOptimizeTask(id) })),
    ...taskIds.map((id) => ({ key: `task:${id}`, run: () => deleteHistoryTask(id) })),
  ];
  const results = await Promise.allSettled(operations.map((operation) => operation.run()));
  const successKeys = operations
    .filter((_, index) => results[index].status === "fulfilled")
    .map((operation) => operation.key);
  const successKeySet = new Set(successKeys);
  const successIds = selectedBeforeDelete
    .filter((item) => {
      if (item.item_type === "prompt_history" && item.history_id) return successKeySet.has(`prompt:${item.history_id}`);
      if (item.item_type === "prompt_optimize_task" && item.history_id) return successKeySet.has(`prompt-optimize:${item.history_id}`);
      return !!item.task_id && successKeySet.has(`task:${item.task_id}`);
    })
    .map((item) => item.image_id)
    .filter((id): id is number => typeof id === "number");
  const failedCount = operations.length - successKeys.length;

  if (successIds.length) {
    selectedImageIds.value = selectedImageIds.value.filter((id) => !successIds.includes(id));
    if (detailItem.value && typeof detailItem.value.image_id === "number" && successIds.includes(detailItem.value.image_id)) {
      detailOpen.value = false;
    }
    if (successIds.length === items.value.length && page.value > 1) page.value -= 1;
  }

  await loadHistory();

  if (failedCount) {
    message.warning(`已删除 ${successKeys.length} 项，${failedCount} 项删除失败`);
    return;
  }
  message.success(`已删除 ${successKeys.length} 项`);
}

function handleBatchDelete() {
  if (isAdminHistoryView.value) {
    message.warning("管理员查看全量历史时暂不支持批量删除");
    return;
  }
  if (!selectedCount.value) {
    message.warning("请先选择需要删除的记录");
    return;
  }
  Modal.confirm({
    title: `确认删除已选中的 ${selectedCount.value} 条历史记录？`,
    content: "普通生图记录会删除整个任务及其结果图；提示词工具记录会删除对应历史记录。同一任务多张结果图只会删除一次。",
    centered: true,
    async onOk() {
      await deleteSelectedItems();
    },
  });
}

function handleReedit(item: UserHistoryCard) {
  if (item.mode === "promptReverse") {
    localStorage.setItem(
      "generateDraftFromHistory",
      JSON.stringify({
        mode: "promptReverse",
        source_image: item.source_image,
        prompt: item.prompt,
      })
    );
  } else if (item.mode === "promptOptimize") {
    localStorage.setItem(
      "generateDraftFromHistory",
      JSON.stringify({
        mode: "generate",
        prompt: item.prompt,
        reference_images: item.source_image ? [item.source_image] : [],
      })
    );
  } else if (item.mode === "inpaint") {
    localStorage.setItem(
      "generateDraftFromHistory",
      JSON.stringify({
        mode: "inpaint",
        prompt: item.prompt,
        size: item.size,
        resolution: item.resolution,
        custom_size: item.custom_size,
        source_image: item.source_image,
        mask_image: item.mask_image,
      })
    );
  } else {
    localStorage.setItem(
      "generateDraftFromHistory",
      JSON.stringify({
        mode: "generate",
        model: item.model,
        prompt: item.prompt,
        reference_images: item.reference_images,
        num_images: item.num_images,
        size: item.size,
        resolution: item.resolution,
        custom_size: item.custom_size,
      })
    );
  }
  router.push("/generate");
}

function handleEditImage(item: UserHistoryCard) {
  if (!canEditHistoryImage(item)) {
    message.warning(item.status === "failed" ? "失败任务暂不支持结果图编辑" : "该任务原图已过期，暂不支持结果图编辑");
    return;
  }
  const referenceImage = isPromptHistoryMode(item.mode)
    ? item.source_image
    : (item.image_url || item.preview_url || item.thumb_url || "");
  if (!referenceImage) {
    message.warning("当前图片暂不可用于图编辑");
    return;
  }
  localStorage.setItem(
    "generateDraftFromHistory",
    JSON.stringify({
      mode: "generate",
      prompt: item.prompt || "",
      reference_images: [referenceImage],
      num_images: 1,
      size: item.size,
      resolution: item.resolution,
      custom_size: item.custom_size,
    })
  );
  router.push("/generate");
}
</script>

<template>
  <div class="warm-page history-page">
    <div class="history-topbar">
      <div class="warm-page-heading">
        <div class="warm-page-icon history-topbar-icon">
          <ClockCircleOutlined />
        </div>
        <div>
          <div class="warm-page-title history-topbar-title">{{ isAdminHistoryView ? "用户任务" : "历史记录" }}</div>
          <div class="warm-page-desc">
            {{ isAdminHistoryView ? "管理员可查看所有用户的历史图片，并按用户或任务条件筛选。" : "按结果图查看历史任务，详情中可查看完整参数并重新编辑。" }}
          </div>
        </div>
      </div>
      <div class="history-topbar-meta">
        <span>共 {{ total }} 条结果</span>
        <span>已展示 {{ items.length }} 条</span>
      </div>
    </div>

    <div class="history-filter-bar">
      <a-select v-model:value="typeFilter" placeholder="全部类型" class="history-filter-control history-filter-select" allow-clear>
        <a-select-option value="text_generate">文生图</a-select-option>
        <a-select-option value="image_edit">图编辑</a-select-option>
        <a-select-option value="inpaint">局部重绘</a-select-option>
        <a-select-option value="promptReverse">提示词反推</a-select-option>
        <a-select-option value="promptOptimize">提示词优化</a-select-option>
      </a-select>
      <a-select v-model:value="sourceFilter" placeholder="全部来源" class="history-filter-control history-filter-select history-filter-select-sm" allow-clear>
        <a-select-option value="web">Web</a-select-option>
        <a-select-option value="app">App</a-select-option>
        <a-select-option value="api">API</a-select-option>
      </a-select>
      <a-select v-model:value="modelFilter" placeholder="全部模型" class="history-filter-control history-filter-select history-filter-select-lg" allow-clear>
        <a-select-option v-for="option in modelOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </a-select-option>
      </a-select>
      <a-select v-model:value="statusFilter" placeholder="全部状态" class="history-filter-control history-filter-select" allow-clear>
        <a-select-option value="pending">等待中</a-select-option>
        <a-select-option value="processing">处理中</a-select-option>
        <a-select-option value="success">成功</a-select-option>
        <a-select-option value="failed">失败</a-select-option>
      </a-select>
      <a-select
        v-if="isAdminHistoryView"
        v-model:value="fallbackFilter"
        placeholder="备用接口"
        class="history-filter-control history-filter-select"
        allow-clear
      >
        <a-select-option value="used">使用了备用接口</a-select-option>
      </a-select>
      <a-select
        v-if="isAdminHistoryView"
        v-model:value="userFilter"
        placeholder="全部用户"
        class="history-filter-control history-filter-select history-filter-select-user"
        allow-clear
        show-search
        option-filter-prop="label"
      >
        <a-select-option
          v-for="user in users"
          :key="user.id"
          :value="user.id"
          :label="user.username"
        >
          {{ user.username }}
        </a-select-option>
      </a-select>
      <a-input
        v-model:value="promptFilter"
        placeholder="按提示词筛选"
        class="history-filter-control history-filter-prompt"
        allow-clear
      />
      <a-range-picker
        v-model:value="dateRangeFilter"
        :placeholder="['开始日期', '结束日期']"
        class="history-filter-control history-filter-date"
      />
      <a-select v-model:value="gridColumnCount" placeholder="每行列数" class="history-filter-control history-filter-columns">
        <a-select-option :value="5">5 列</a-select-option>
        <a-select-option :value="6">6 列</a-select-option>
        <a-select-option :value="7">7 列</a-select-option>
        <a-select-option :value="8">8 列</a-select-option>
      </a-select>
      <a-button class="history-filter-btn history-filter-btn-secondary" @click="resetFilters">重置</a-button>
      <a-tooltip :title="batchMode ? '退出批量模式' : '进入批量模式'">
        <a-button
          type="text"
          class="history-filter-btn batch-mode-btn"
          :class="{ active: batchMode }"
          @click="toggleBatchMode"
        >
          <template #icon><CheckSquareOutlined /></template>
        </a-button>
      </a-tooltip>
    </div>

    <transition name="history-panel-slide">
      <div v-if="batchMode && items.length" class="history-batch-bar warm-card">
        <div class="history-batch-summary">
          <span>已选 {{ selectedCount }} 项</span>
          <span>当前页 {{ selectableCount }} 项</span>
        </div>
        <div class="history-batch-actions">
          <a-button
            size="small"
            class="history-batch-btn history-batch-btn-secondary"
            :disabled="!items.length || allVisibleSelected"
            @click="selectAllVisible"
          >
            全选
          </a-button>
          <a-button size="small" class="history-batch-btn history-batch-btn-secondary" :disabled="!items.length" @click="invertVisibleSelection">
            反选
          </a-button>
          <a-button size="small" class="history-batch-btn history-batch-btn-secondary" :disabled="!selectedCount" @click="clearSelection">
            清空
          </a-button>
          <a-button
            size="small"
            class="history-batch-btn history-batch-btn-primary"
            :disabled="!downloadableSelectedItems.length"
            @click="handleBatchDownload"
          >
            批量下载
          </a-button>
          <a-button
            v-if="!isAdminHistoryView"
            danger
            size="small"
            class="history-batch-btn history-batch-btn-danger"
            :disabled="!selectedCount"
            @click="handleBatchDelete"
          >
            批量删除
          </a-button>
        </div>
      </div>
    </transition>

    <a-spin :spinning="loading">
      <div v-if="!items.length && !loading" class="empty-state warm-card">
        <a-empty :description="activeFilterCount ? '没有符合条件的历史记录' : '暂无生成记录'" />
      </div>

      <TransitionGroup v-else name="history-card" tag="div" class="history-grid" :style="historyGridStyle">
        <div
          v-for="(item, index) in items"
          :key="getHistoryItemKey(item)"
          class="result-card warm-card"
          :style="{ '--history-card-delay': `${Math.min(index, 9) * 45}ms` }"
          @click="openDetail(item)"
        >
          <div
            class="result-card-media"
            :class="{
              'result-card-media-failed': item.status === 'failed',
              'result-card-media-pending': isHistoryItemPending(item.status),
            }"
            :style="{
              '--history-pending-bg-image': `url('${generateEmptyStateAsset}')`,
            }"
          >
            <button
              v-if="isAdminHistoryView"
              type="button"
              class="result-card-user"
              @click.stop="openUserInfoDialog(item)"
            >
              <a-avatar :size="22" :src="item.avatar_url || undefined" class="result-card-user-avatar">
                {{ item.username?.charAt(0)?.toUpperCase() }}
              </a-avatar>
              <span class="result-card-user-name">{{ item.username || "未知用户" }}</span>
            </button>
            <div v-if="batchMode" class="result-card-select" @click.stop>
              <a-checkbox
                :checked="typeof item.image_id === 'number' ? isSelected(item.image_id) : false"
                :disabled="typeof item.image_id !== 'number'"
                @change="typeof item.image_id === 'number' && handleSelectChange(item.image_id, $event)"
              />
            </div>
            <img
              v-if="getHistoryCardMedia(item)"
              :src="getHistoryCardMedia(item)"
              :alt="isPromptHistoryMode(item.mode) ? `${modeLabel(item.task_type)}参考图` : item.status === 'failed' ? '生成失败' : '历史结果图'"
              :class="{ 'failed-result-image': item.status === 'failed' }"
              loading="lazy"
            />
            <div v-else-if="shouldShowHistoryLargeImagePreviewNotice(item)" class="result-card-preview-notice">
              <span>{{ LARGE_IMAGE_PREVIEW_NOTICE }}</span>
            </div>
            <div v-else class="result-card-placeholder">
              <template v-if="isHistoryItemPending(item.status)">
                <a-spin
                  :indicator="h(LoadingOutlined, { style: { fontSize: '28px', color: '#7c8db5' } })"
                />
              </template>
              <ClockCircleOutlined v-else />
            </div>

            <div v-if="getModelLabel(item.model)" class="result-card-model-badge" :title="getModelLabel(item.model)">
              {{ getModelLabel(item.model) }}
            </div>
            <div
              v-if="isAdminHistoryView && formatRunTime(item.run_time)"
              class="result-card-run-time"
              :title="formatRunTime(item.run_time)"
            >
              {{ formatRunTime(item.run_time) }}
            </div>

            <a-tooltip v-if="canPinHistoryItem(item) && item.is_pinned" title="取消置顶">
              <a-button
                shape="circle"
                type="text"
                class="history-overlay-btn history-overlay-btn-active history-overlay-btn-persistent"
                :loading="isPinning(item)"
                @click.stop="handleTogglePin(item)"
              >
                <template #icon><PushpinOutlined /></template>
              </a-button>
            </a-tooltip>

            <div
              class="history-overlay-actions history-overlay-actions-top"
              :class="{ 'history-overlay-actions-with-persistent-pin': canPinHistoryItem(item) && item.is_pinned }"
            >
              <a-tooltip v-if="!isAdminHistoryView && item.task_id" title="反馈">
                <a-button
                  shape="circle"
                  type="text"
                  class="history-overlay-btn"
                  :class="{ 'history-overlay-btn-failed': item.status === 'failed' }"
                  @click.stop="openFeedbackDialog(item)"
                >
                  <template #icon><MessageOutlined /></template>
                </a-button>
              </a-tooltip>
              <a-tooltip v-if="canPinHistoryItem(item) && !item.is_pinned" title="置顶到顶部">
                <a-button
                  shape="circle"
                  type="text"
                  class="history-overlay-btn"
                  :loading="isPinning(item)"
                  @click.stop="handleTogglePin(item)"
                >
                  <template #icon><PushpinOutlined /></template>
                </a-button>
              </a-tooltip>
              <a-tooltip v-if="!isAdminHistoryView && !isHistoryItemPending(item.status)" title="删除">
                <a-button shape="circle" type="text" class="history-overlay-btn history-overlay-btn-danger" @click.stop="handleDelete(item)">
                  <template #icon><DeleteOutlined /></template>
                </a-button>
              </a-tooltip>
            </div>

            <div class="history-overlay-actions history-overlay-actions-bottom">
              <a-tooltip v-if="canHistoryViewOriginal(item)" title="查看原图">
                <a-button shape="circle" type="text" class="history-overlay-btn" @click.stop="handleViewOriginal(item)">
                  <template #icon><EyeOutlined /></template>
                </a-button>
              </a-tooltip>
              <a-tooltip v-if="item.status === 'success' && canEditHistoryImage(item)" title="结果图编辑">
                <a-button shape="circle" type="text" class="history-overlay-btn" @click.stop="handleEditImage(item)">
                  <template #icon><EditOutlined /></template>
                </a-button>
              </a-tooltip>
              <a-tooltip v-if="canCreateTemplateFromHistory(item)" title="设为创意模版">
                <a-button shape="circle" type="text" class="history-overlay-btn" @click.stop="handleCreateTemplateFromHistory(item)">
                  <template #icon><PictureOutlined /></template>
                </a-button>
              </a-tooltip>
              <a-tooltip title="重新生成">
                <a-button shape="circle" type="text" class="history-overlay-btn" @click.stop="handleReedit(item)">
                  <template #icon><ReloadOutlined /></template>
                </a-button>
              </a-tooltip>
              <a-tooltip v-if="item.status !== 'failed'" title="下载原图">
                <a-button
                  shape="circle"
                  type="text"
                  class="history-overlay-btn"
                  :disabled="isHistoryItemExpired(item) || !item.image_url || isPromptHistoryMode(item.mode) || typeof item.image_id !== 'number'"
                  @click.stop="typeof item.image_id === 'number' && download(item.image_id, item.image_url)"
                >
                  <template #icon><DownloadOutlined /></template>
                </a-button>
              </a-tooltip>
            </div>
          </div>
        </div>
      </TransitionGroup>
    </a-spin>

    <div v-if="loadingMore" class="history-load-more-tip">
      <a-spin size="small" />
      <span>正在加载更多历史记录...</span>
    </div>
    <div v-else-if="items.length && !hasMoreHistory" class="history-load-more-tip history-load-more-tip-finished">
      已加载全部历史记录
    </div>
    <div
      v-if="items.length && hasMoreHistory"
      ref="loadMoreAnchor"
      class="history-load-more-anchor"
      aria-hidden="true"
    />

    <HistoryDetailDialog
      :open="detailOpen"
      :item="detailItem"
      :loading="detailLoading"
      :model-options="modelOptions"
      :show-error-message="isAdminHistoryView"
      show-actions
      @update:open="detailOpen = $event"
      @reedit="handleReedit"
      @download="handleDetailDownload"
    />

    <div v-if="previewVisible" style="display: none">
      <a-image
        :src="previewSrc"
        :preview="{ visible: previewVisible, onVisibleChange: (v: boolean) => (previewVisible = v) }"
      />
    </div>
    <FeedbackDialog
      v-model:open="feedbackDialogOpen"
      :task-id="feedbackTarget?.task_id"
      :model="feedbackTarget?.model"
      :prompt="feedbackTarget?.prompt"
      :created-at="feedbackTarget?.created_at"
    />
    <TemplateEditorDialog ref="templateDialogRef" />

    <AdminUserInfoDialog
      v-model:open="userInfoDialogOpen"
      :user="selectedUserInfo"
      @view-data="handleViewUserData"
    />
  </div>
</template>

<style scoped lang="scss">
.history-page {
  gap: 10px;
  animation: history-page-enter var(--motion-duration-reveal) ease both;
}

@keyframes history-page-enter {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes history-fade-up {
  from {
    opacity: 0;
    transform: translate3d(0, 16px, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
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

.history-topbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 3px;
  animation: history-fade-up var(--motion-duration-reveal) var(--motion-ease-enter) 0.04s both;
}

.history-topbar-icon {
  width: 38px;
  height: 38px;
  border-radius: 13px;
  font-size: 17px;
}

.history-topbar-title {
  font-size: 19px;
  line-height: 1.3;
}

.history-topbar .warm-page-desc {
  font-size: 13px;
  line-height: 1.6;
}

.history-topbar-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #9b825f;
  padding-top: 3px;
}

.history-filter-bar {
  display: flex;
  gap: 10px;
  row-gap: 5px;
  flex-wrap: nowrap;
  align-items: center;
  margin-bottom: 9px;
  animation: history-fade-up var(--motion-duration-reveal-soft) var(--motion-ease-enter) 0.12s both;

  :deep(.ant-select-single:not(.ant-select-customize-input) .ant-select-selector) {
    height: 30px !important;
    min-height: 30px !important;
  }

  :deep(.ant-select-selection-item),
  :deep(.ant-select-selection-placeholder) {
    line-height: 28px !important;
  }

  :deep(.ant-select-selection-search-input) {
    height: 28px !important;
  }

  :deep(.ant-input),
  :deep(.ant-input-affix-wrapper) {
    height: 30px !important;
    min-height: 30px !important;
    padding-block: 0 !important;
  }

  :deep(.ant-input-affix-wrapper .ant-input) {
    height: 28px !important;
    line-height: 28px !important;
  }

  :deep(.ant-input-affix-wrapper .ant-input-suffix) {
    line-height: 28px;
  }

  :deep(.history-filter-prompt.ant-input-affix-wrapper) {
    overflow: hidden;
  }

  :deep(.history-filter-prompt.ant-input-affix-wrapper .ant-input) {
    height: 28px !important;
    line-height: 28px !important;
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
  }

  :deep(.history-filter-prompt.ant-input-affix-wrapper .ant-input:hover),
  :deep(.history-filter-prompt.ant-input-affix-wrapper .ant-input:focus) {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    transform: none !important;
  }

  :deep(.history-filter-prompt.ant-input-affix-wrapper:hover) {
    transform: none !important;
  }

  :deep(.history-filter-prompt.ant-input-affix-wrapper-focused) {
    transform: none !important;
    box-shadow: 0 0 0 3px var(--theme-focus-ring) !important;
  }

  :deep(.ant-picker) {
    height: 30px !important;
    min-height: 30px !important;
    padding-block: 0 !important;
  }

  :deep(.ant-picker .ant-picker-input > input) {
    height: 28px !important;
    line-height: 28px !important;
  }
}

.history-filter-control {
  flex: 0 1 auto;
  min-width: 0;
}

.history-filter-select {
  width: clamp(112px, 8.2vw, 160px);
}

.history-filter-select-sm {
  width: clamp(104px, 7.2vw, 140px);
}

.history-filter-select-lg {
  width: clamp(180px, 13.2vw, 255px);
}

.history-filter-select-user {
  width: clamp(132px, 9.8vw, 190px);
}

.history-filter-prompt {
  flex: 1 1 150px;
  width: clamp(140px, 11vw, 220px);
}

.history-filter-date {
  width: clamp(210px, 14vw, 250px);
}

.history-filter-columns {
  width: 70px;
}

.history-filter-tip {
  font-size: 13px;
  color: #9b825f;
}

.history-filter-btn {
  height: 30px;
  border-radius: 11px;
  font-size: 13px;
  font-weight: 600;
  box-shadow: none;
  transition:
    transform var(--motion-duration-press) var(--motion-ease-soft),
    box-shadow var(--motion-duration-base) var(--motion-ease-soft),
    background var(--motion-duration-base) var(--motion-ease-soft),
    border-color var(--motion-duration-base) var(--motion-ease-soft),
    color var(--motion-duration-base) var(--motion-ease-soft),
    opacity var(--motion-duration-base) var(--motion-ease-soft);

  &:active {
    transform: scale(0.96);
  }
}

.history-filter-btn-primary {
  border-color: var(--theme-accent) !important;
  background: var(--theme-accent) !important;
  color: var(--theme-accent-contrast) !important;

  &:hover,
  &:focus {
    border-color: var(--theme-accent-strong) !important;
    background: var(--theme-accent-strong) !important;
    color: var(--theme-accent-contrast) !important;
  }
}

.history-filter-btn-secondary {
  border-color: var(--theme-panel-border-strong) !important;
  background: var(--theme-panel-bg-strong) !important;
  color: var(--theme-accent-text) !important;

  &:hover,
  &:focus {
    border-color: var(--theme-border-strong) !important;
    background: var(--theme-control-hover-bg) !important;
    color: var(--theme-accent-text-hover) !important;
  }
}

.batch-mode-btn {
  width: 30px;
  border-radius: 10px;
  padding: 0 !important;
  border-color: var(--theme-panel-border-strong) !important;
  background: var(--theme-panel-bg-strong) !important;
  color: var(--theme-accent-text) !important;
  transition:
    transform var(--motion-duration-press) var(--motion-ease-soft),
    box-shadow var(--motion-duration-base) var(--motion-ease-soft),
    background var(--motion-duration-base) var(--motion-ease-soft),
    border-color var(--motion-duration-base) var(--motion-ease-soft),
    color var(--motion-duration-base) var(--motion-ease-soft);

  &:hover,
  &:focus {
    border-color: var(--theme-border-strong) !important;
    color: var(--theme-accent-text-hover) !important;
    background: var(--theme-control-hover-bg) !important;
    transform: translateY(-1px);
  }

  &.active {
    border-color: var(--theme-accent) !important;
    background: var(--theme-accent) !important;
    color: var(--theme-accent-contrast) !important;
    box-shadow: 0 10px 22px var(--theme-shadow-strong);
  }

  &:active {
    transform: scale(0.94);
  }
}

.empty-state {
  padding: 72px 0;
  text-align: center;
  animation: history-fade-up var(--motion-duration-reveal) var(--motion-ease-enter) 0.2s both;
}

.history-batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding: 10px 12px;
  transform-origin: top center;
}

.history-batch-summary {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text-secondary);
}

.history-batch-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.history-batch-btn {
  min-width: 64px;
  border-radius: 10px;
  height: 30px;
  font-size: 12px;
  font-weight: 600;
  box-shadow: none;
  transition:
    transform var(--motion-duration-press) var(--motion-ease-soft),
    box-shadow var(--motion-duration-base) var(--motion-ease-soft),
    background var(--motion-duration-base) var(--motion-ease-soft),
    border-color var(--motion-duration-base) var(--motion-ease-soft),
    color var(--motion-duration-base) var(--motion-ease-soft),
    opacity var(--motion-duration-base) var(--motion-ease-soft);

  &:active {
    transform: scale(0.96);
  }
}

.history-batch-btn-secondary {
  border-color: var(--theme-panel-border-strong) !important;
  background: var(--theme-panel-bg-strong) !important;
  color: var(--theme-accent-text) !important;

  &:hover,
  &:focus {
    border-color: var(--theme-border-strong) !important;
    background: var(--theme-control-hover-bg) !important;
    color: var(--theme-accent-text-hover) !important;
  }

  &[disabled] {
    border-color: var(--theme-control-border) !important;
    background: var(--theme-panel-bg-soft) !important;
    color: var(--text-muted) !important;
  }
}

.history-batch-btn-primary {
  border-color: var(--theme-accent) !important;
  background: var(--theme-accent) !important;
  color: var(--theme-accent-contrast) !important;

  &:hover,
  &:focus {
    border-color: var(--theme-accent-strong) !important;
    background: var(--theme-accent-strong) !important;
    color: var(--theme-accent-contrast) !important;
  }

  &[disabled] {
    border-color: var(--theme-control-border) !important;
    background: var(--theme-control-hover-bg) !important;
    color: var(--text-muted) !important;
  }
}

.history-batch-btn-danger {
  border-color: #efb2a9 !important;
  background: #fff4f2 !important;
  color: #c25b4e !important;

  &:hover,
  &:focus {
    border-color: #e38779 !important;
    background: #ffe8e4 !important;
    color: #d6574b !important;
  }

  &[disabled] {
    border-color: #f5d5cf !important;
    background: #fff8f6 !important;
    color: #d8aaa2 !important;
  }
}

.history-grid {
  display: grid;
  grid-template-columns: repeat(var(--history-grid-columns, 6), minmax(0, 1fr));
  gap: 12px;
}

.history-grid .result-card.warm-card {
  border: none;
  background: transparent;
  box-shadow: none;
}

.result-card {
  position: relative;
  padding: 0;
  overflow: visible;
  cursor: pointer;
  will-change: transform;
  transition:
    transform var(--motion-duration-hover) var(--motion-ease-enter),
    box-shadow var(--motion-duration-hover) var(--motion-ease-soft),
    filter var(--motion-duration-hover) var(--motion-ease-soft);

  &:hover {
    transform: translateY(-6px);
    box-shadow: none;
  }

  &:active {
    transform: translateY(-2px) scale(0.992);
  }

  &:hover .result-card-media:not(.result-card-media-failed) {
    box-shadow: 0 16px 28px var(--theme-shadow-medium);
    border-color: var(--theme-border-strong);
  }

  &:hover .result-card-media.result-card-media-failed {
    box-shadow: 0 16px 28px rgba(214, 87, 75, 0.18);
    border-color: rgba(214, 87, 75, 0.48);
  }

  &:hover .result-card-media img {
    transform: scale(1.02);
  }

  &:hover .result-card-model-badge,
  &:hover .result-card-run-time {
    opacity: 0;
    transform: translateY(6px);
  }
}

.result-card-user {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 7px;
  max-width: calc(100% - 24px);
  min-width: 0;
  padding: 5px 8px 5px 5px;
  border: 1px solid rgba(255, 240, 214, 0.18);
  border-radius: 999px;
  background: rgba(76, 52, 26, 0.58);
  color: #fff7ea;
  box-shadow: 0 10px 20px rgba(34, 22, 10, 0.22);
  backdrop-filter: blur(10px);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform var(--motion-duration-fast) var(--motion-ease-soft),
    background var(--motion-duration-fast) var(--motion-ease-soft);
}

.result-card-user:hover {
  transform: translateY(-1px);
  background: rgba(76, 52, 26, 0.72);
}

.result-card-user-avatar {
  flex: 0 0 auto;
  background: var(--theme-accent);
  color: var(--theme-accent-contrast);
}

.result-card-user-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .history-page .result-card-user {
  border-color: var(--theme-panel-border);
  background: rgba(var(--theme-surface-strong-rgb), 0.9);
  color: var(--theme-accent-text);
  box-shadow: 0 10px 20px var(--theme-shadow-soft);
}

html:is([data-theme="dark"], [data-theme="midnight"]) .history-page .result-card-model-badge,
html:is([data-theme="dark"], [data-theme="midnight"]) .history-page .result-card-run-time {
  border-color: var(--theme-panel-border);
  background: rgba(var(--theme-surface-strong-rgb), 0.9);
  color: var(--theme-accent-text);
  box-shadow: 0 10px 20px var(--theme-shadow-soft);
}

.result-card-select {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 3;
  padding: 5px 7px;
  border-radius: 12px;
  background: rgba(var(--theme-surface-strong-rgb), 0.88);
  border: 1px solid var(--theme-panel-border);
  box-shadow: 0 6px 16px rgba(76, 52, 26, 0.08);
  backdrop-filter: blur(8px);
}

.result-card-model-badge,
.result-card-run-time {
  position: absolute;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  max-width: calc(100% - 24px);
  min-height: 24px;
  padding: 0 8px;
  border: 1px solid rgba(255, 240, 214, 0.18);
  border-radius: 999px;
  background: rgba(76, 52, 26, 0.58);
  color: #fff7ea;
  box-shadow: 0 10px 20px rgba(34, 22, 10, 0.22);
  backdrop-filter: blur(10px);
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: none;
  transition:
    opacity var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft);
}

.result-card-model-badge {
  left: 12px;
  bottom: 12px;
}

.result-card-run-time {
  top: 12px;
  right: 12px;
}

.result-card-media {
  --media-radius: 16px;
  width: 100%;
  aspect-ratio: 1 / 1;
  box-sizing: border-box;
  border-radius: var(--media-radius);
  overflow: hidden;
  border: 1px dashed var(--theme-panel-border);
  background:
    radial-gradient(circle at 50% 45%, rgba(var(--theme-surface-strong-rgb), 0.98) 0%, rgba(var(--theme-page-base-rgb), 0.98) 58%, rgba(var(--theme-page-base-rgb), 0.96) 100%),
    linear-gradient(180deg, var(--theme-panel-bg), var(--theme-panel-bg-strong));
  box-shadow: 0 12px 24px var(--theme-shadow-soft);
  cursor: pointer;
  position: relative;
  transition:
    box-shadow var(--motion-duration-hover) var(--motion-ease-soft),
    border-color var(--motion-duration-hover) var(--motion-ease-soft),
    transform var(--motion-duration-emphasis) var(--motion-ease-enter);

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-position: center;
    box-sizing: border-box;
    display: block;
    border-radius: calc(var(--media-radius) - 1px);
    background: transparent;
    transition: transform var(--motion-duration-emphasis) var(--motion-ease-enter);
  }

  &.result-card-media-failed {
    border-style: dashed;
    border-color: rgba(201, 73, 60, 0.72);
    border-width: 1px;
    background: linear-gradient(180deg, #fff0ed, #ffe1db);
    box-shadow: 0 14px 26px rgba(214, 87, 75, 0.16);
  }

  &.result-card-media-pending {
    background:
      linear-gradient(180deg, rgba(255, 252, 246, 0.24), rgba(255, 248, 238, 0.34)),
      linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg));
  }

  &.result-card-media-pending::before {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--history-pending-bg-image) center / cover no-repeat;
    opacity: 0.5;
    pointer-events: none;
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
  color: var(--text-secondary);
  text-align: center;
  font-size: 28px;
  background: linear-gradient(180deg, rgba(255, 250, 240, 0.1), rgba(255, 250, 240, 0.16));
  backdrop-filter: blur(0.25px);
  border-radius: calc(var(--media-radius, 18px) - 1px);
}

.failed-result-image {
  object-fit: contain !important;
  padding: 28px;
  background: linear-gradient(180deg, #fff2ef, #ffdcd5);
  border-radius: calc(var(--media-radius, 18px) - 2px);
  opacity: 0.96;
}

.history-overlay-actions {
  position: absolute;
  display: flex;
  gap: 8px;
  z-index: 2;
  opacity: 0;
  transform: translateY(6px);
  pointer-events: none;
  transition:
    opacity var(--motion-duration-fast) var(--motion-ease-soft),
    transform var(--motion-duration-fast) var(--motion-ease-soft);
}

.history-overlay-actions-top {
  top: 12px;
  right: 12px;
}

.history-overlay-actions-bottom {
  right: 12px;
  bottom: 12px;
}

.history-overlay-actions-with-persistent-pin {
  right: 50px;
}

.result-card:hover .history-overlay-actions,
.result-card:focus-within .history-overlay-actions {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.history-overlay-btn-persistent {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 3;
}

.history-feedback-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
}

.history-overlay-btn {
  width: 32px !important;
  height: 32px !important;
  min-width: 32px !important;
  max-width: 32px !important;
  min-height: 32px !important;
  max-height: 32px !important;
  padding: 0 !important;
  line-height: 0 !important;
  border-radius: 50% !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  flex-shrink: 0;
  border: 1px solid rgba(255, 240, 214, 0.18) !important;
  background: rgba(76, 52, 26, 0.58) !important;
  color: #fff7ea !important;
  box-shadow: 0 10px 20px rgba(34, 22, 10, 0.22);
  backdrop-filter: blur(10px);
  transition:
    transform var(--motion-duration-press) var(--motion-ease-soft),
    background var(--motion-duration-fast) var(--motion-ease-soft),
    border-color var(--motion-duration-fast) var(--motion-ease-soft),
    color var(--motion-duration-fast) var(--motion-ease-soft),
    box-shadow var(--motion-duration-fast) var(--motion-ease-soft);

  :deep(.anticon),
  :deep(.ant-btn-icon) {
    line-height: 0;
    font-size: 14px;
  }

  &:hover,
  &:focus {
    background: rgba(76, 52, 26, 0.78) !important;
    border-color: rgba(255, 240, 214, 0.26) !important;
    color: #fffdfa !important;
    transform: translateY(-1px);
    box-shadow: 0 14px 26px rgba(34, 22, 10, 0.28);
  }

  &:active {
    transform: scale(0.93);
  }

  &[disabled] {
    border-color: rgba(255, 240, 214, 0.08) !important;
    background: rgba(56, 40, 24, 0.34) !important;
    color: rgba(255, 247, 234, 0.45) !important;
    box-shadow: none;
    opacity: 1;
  }
}

.history-overlay-btn-danger {
  border-color: rgba(255, 214, 209, 0.18) !important;
  background: rgba(180, 58, 43, 0.88) !important;
  color: #fff5f2 !important;
  box-shadow: 0 12px 24px rgba(140, 40, 28, 0.28);

  &:hover,
  &:focus {
    background: rgba(201, 73, 60, 0.98) !important;
    border-color: rgba(255, 224, 220, 0.24) !important;
    color: #fff7f5 !important;
    box-shadow: 0 16px 28px rgba(140, 40, 28, 0.36);
  }
}

.history-overlay-btn-active {
  border-color: rgba(255, 214, 76, 0.98) !important;
  background: linear-gradient(180deg, rgba(255, 212, 59, 0.96), rgba(245, 176, 0, 0.96)) !important;
  color: #6b4200 !important;
  box-shadow: 0 14px 28px rgba(255, 196, 0, 0.38);

  &:hover,
  &:focus {
    background: linear-gradient(180deg, rgba(255, 228, 118, 0.98), rgba(255, 194, 36, 0.98)) !important;
    border-color: rgba(255, 228, 118, 0.98) !important;
    color: #5a3500 !important;
    box-shadow: 0 16px 30px rgba(255, 196, 0, 0.42);
  }
}

.history-feedback-btn.history-overlay-btn-failed {
  border-color: rgba(255, 214, 209, 0.18) !important;
  background: rgba(180, 58, 43, 0.88) !important;
  color: #fff5f2 !important;
  box-shadow: 0 10px 22px rgba(140, 40, 28, 0.24);

  &:hover,
  &:focus {
    background: rgba(201, 73, 60, 0.98) !important;
    border-color: rgba(255, 224, 220, 0.24) !important;
    color: #fff7f5 !important;
    box-shadow: 0 14px 26px rgba(140, 40, 28, 0.34);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .history-page .history-overlay-btn {
  border-color: var(--theme-panel-border) !important;
  background: rgba(var(--theme-surface-strong-rgb), 0.9) !important;
  color: var(--theme-accent-text) !important;
  box-shadow: 0 10px 20px var(--theme-shadow-soft);

  &:hover,
  &:focus {
    background: var(--theme-surface-strong) !important;
    border-color: var(--theme-border-strong) !important;
    color: var(--theme-accent-text-hover) !important;
    box-shadow: 0 14px 26px var(--theme-shadow-medium);
  }

  &[disabled] {
    border-color: var(--theme-panel-border) !important;
    background: rgba(var(--theme-surface-strong-rgb), 0.42) !important;
    color: var(--text-muted) !important;
    box-shadow: none;
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .history-page .history-overlay-btn-danger,
html:is([data-theme="dark"], [data-theme="midnight"]) .history-page .history-feedback-btn.history-overlay-btn-failed {
  border-color: rgba(222, 143, 132, 0.24) !important;
  background: rgba(185, 56, 42, 0.82) !important;
  color: #fff5f2 !important;
  box-shadow: 0 12px 24px rgba(140, 40, 28, 0.3);

  &:hover,
  &:focus {
    background: rgba(185, 56, 42, 0.92) !important;
    border-color: rgba(240, 176, 166, 0.3) !important;
    color: #fff7f5 !important;
    box-shadow: 0 16px 28px rgba(140, 40, 28, 0.38);
  }
}

html:is([data-theme="dark"], [data-theme="midnight"]) .history-page .history-overlay-btn-active {
  border-color: var(--theme-border-accent) !important;
  background: var(--theme-accent) !important;
  color: var(--theme-accent-contrast) !important;
  box-shadow: 0 14px 28px var(--theme-shadow-strong);

  &:hover,
  &:focus {
    background: var(--theme-accent-strong) !important;
    border-color: var(--theme-border-accent) !important;
    color: #ffffff !important;
    box-shadow: 0 16px 30px var(--theme-shadow-strong);
  }
}

.detail-section + .detail-section {
  margin-top: 18px;
}

.detail-layout {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 20px;
  align-items: start;
  padding-bottom: 0;
  animation: history-detail-slide-in var(--motion-duration-reveal-slower) var(--motion-ease-enter) both;
}

.detail-left,
.detail-right {
  min-width: 0;
}

.detail-right {
  display: flex;
  flex-direction: column;
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
  transition:
    transform var(--motion-duration-press) var(--motion-ease-soft),
    background var(--motion-duration-fast) var(--motion-ease-soft),
    color var(--motion-duration-fast) var(--motion-ease-soft),
    box-shadow var(--motion-duration-fast) var(--motion-ease-soft);

  &:hover {
    background: var(--theme-panel-bg-strong) !important;
    color: var(--theme-link-hover) !important;
    transform: translateY(-1px);
    box-shadow: 0 10px 20px var(--theme-shadow-soft);
  }

  &:active {
    transform: scale(0.96);
  }
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
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.detail-result-card {
  height: clamp(220px, 36vh, 340px);
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);
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
    transition: transform var(--motion-duration-hover) var(--motion-ease-soft);
  }

  &.pending {
    cursor: default;
  }

  &:not(.pending):hover {
    transform: translateY(-3px);
    border-color: var(--theme-border-strong);
    box-shadow: 0 16px 28px var(--theme-shadow-medium);
  }

  &:not(.pending):hover img {
    transform: scale(1.015);
  }

  &.failed img {
    object-fit: contain;
    padding: 18px;
    background: var(--theme-panel-bg);
  }

  &.single {
    height: clamp(440px, 72vh, 680px);
  }
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--theme-panel-bg-soft);
  border: 1px solid var(--theme-panel-border);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.8;

  span:not(:last-child)::after {
    content: "｜";
    margin: 0 8px;
    color: #d3b487;
  }
}

.warm-pagination {
  animation: history-fade-up var(--motion-duration-reveal-soft) var(--motion-ease-enter) 0.26s both;
}

.history-load-more-tip {
  margin-top: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
}

.history-load-more-tip-finished {
  color: var(--text-muted);
}

.history-load-more-anchor {
  width: 100%;
  height: 1px;
  margin-top: 1px;
}

.result-card-preview-notice {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 22px;
  color: var(--theme-text-secondary);
  text-align: center;
  font-size: 13px;
  line-height: 1.7;
  background:
    linear-gradient(180deg, rgba(var(--theme-surface-strong-rgb), 0.78), rgba(var(--theme-page-base-rgb), 0.92)),
    linear-gradient(180deg, var(--theme-panel-bg-soft), var(--theme-panel-bg));
  border-radius: calc(var(--media-radius, 18px) - 1px);
}

.history-card-enter-active,
.history-card-leave-active {
  transition:
    opacity var(--motion-duration-emphasis) var(--motion-ease-soft),
    transform var(--motion-duration-emphasis-plus) var(--motion-ease-enter);
  transition-delay: var(--history-card-delay, 0ms);
}

.history-card-enter-from,
.history-card-leave-to {
  opacity: 0;
  transform: translate3d(0, 22px, 0) scale(0.985);
}

.history-card-move {
  transition: transform var(--motion-duration-reveal-fast) var(--motion-ease-enter);
}

.history-panel-slide-enter-active,
.history-panel-slide-leave-active {
  transition:
    opacity var(--motion-duration-slide) var(--motion-ease-soft),
    transform var(--motion-duration-slide) var(--motion-ease-enter),
    filter var(--motion-duration-slide) var(--motion-ease-soft);
}

.history-panel-slide-enter-from,
.history-panel-slide-leave-to {
  opacity: 0;
  transform: translate3d(0, -14px, 0) scale(0.985);
  filter: blur(6px);
}

@media (prefers-reduced-motion: reduce) {
  .history-page,
  .history-topbar,
  .history-filter-bar,
  .empty-state,
  .warm-pagination,
  .detail-layout {
    animation: none !important;
  }

  .history-card-enter-active,
  .history-card-leave-active,
  .history-card-move,
  .history-panel-slide-enter-active,
  .history-panel-slide-leave-active,
  .result-card,
  .result-card-media img,
  .result-card-body,
  .result-card-model,
  .history-filter-btn,
  .batch-mode-btn,
  .history-batch-btn,
  .ghost-icon-btn,
  .detail-copy-btn,
  .detail-thumb,
  .detail-result-card,
  .detail-result-card img {
    transition: none !important;
  }
}

@media (max-width: 900px) {
  .history-topbar {
    flex-direction: column;
    align-items: stretch;
  }

  .history-filter-bar {
    flex-wrap: wrap;
  }

  .history-filter-select,
  .history-filter-select-sm,
  .history-filter-select-lg,
  .history-filter-select-user,
  .history-filter-prompt,
  .history-filter-date {
    flex: 1 1 160px;
    width: auto;
  }

  .history-filter-columns {
    width: 70px;
  }

  .history-batch-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .history-batch-actions {
    justify-content: flex-start;
  }

  .history-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  }

  .detail-layout {
    grid-template-columns: 1fr;
  }

  .detail-floating-actions {
    position: static;
    justify-content: flex-end;
    margin-top: 14px;
    padding: 0;
  }

  .detail-result-grid {
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }
}

</style>
