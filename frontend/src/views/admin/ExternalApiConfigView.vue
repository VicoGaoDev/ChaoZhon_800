<script setup lang="ts">
import { computed, h, onMounted, reactive, ref, watch } from "vue";
import { message, Modal } from "ant-design-vue";
import {
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  EyeInvisibleOutlined,
  EyeOutlined,
  PlusOutlined,
  SaveOutlined,
} from "@ant-design/icons-vue";
import {
  createExternalApiConfig,
  createExternalApiSceneBinding,
  deleteExternalApiConfig,
  deleteExternalApiSceneBinding,
  getExternalApiSecrets,
  listExternalApiConfigs,
  listExternalApiSceneBindings,
  setExternalApiSecrets,
  testExternalApiConfig,
  updateExternalApiConfig,
  updateExternalApiConfigStatus,
  updateExternalApiSceneBinding,
  updateExternalApiSceneBindingMeta,
  updateExternalApiSceneBindingStatus,
} from "@/api/admin";
import {
  parseAdminConfigTemplate,
  stringifyAdminConfigTemplate,
} from "@/lib/adminConfigTemplate";
import type {
  ExternalApiConfig,
  ExternalApiConfigPayload,
  ExternalApiConfigTestResult,
  ExternalApiRequestFormat,
  ExternalApiSceneBinding,
  ExternalApiSceneBindingCreatePayload,
  ExternalApiSceneBindingMetaPayload,
  ExternalApiSceneType,
} from "@/types";

const DEFAULT_ASPECT_RATIO_OPTIONS_JSON = JSON.stringify([
  { label: "■  1:1", value: "1:1" },
  { label: "▮  2:3", value: "2:3" },
  { label: "▬  3:2", value: "3:2" },
  { label: "▮  3:4", value: "3:4" },
  { label: "▬  4:3", value: "4:3" },
  { label: "▮  9:16", value: "9:16" },
  { label: "▬  16:9", value: "16:9" },
], null, 2);

const DEFAULT_IMAGE_SIZE_OPTIONS_JSON = JSON.stringify([
  { label: "1K", value: "1K" },
  { label: "2K", value: "2K" },
  { label: "4K", value: "4K" },
], null, 2);

const DEFAULT_CUSTOM_SIZE_OPTIONS_JSON = JSON.stringify([
  { label: "1024 x 1024", value: "1024x1024" },
  { label: "1152 x 896", value: "1152x896" },
  { label: "896 x 1152", value: "896x1152" },
  { label: "1280 x 720", value: "1280x720" },
], null, 2);
const DEFAULT_RESOLUTION_MAPPING_JSON = JSON.stringify({}, null, 2);
const DEFAULT_RESOLUTION_CREDIT_COSTS_JSON = JSON.stringify({}, null, 2);
const DEFAULT_IMAGE_EDIT_MAX_REFERENCE_IMAGES = 6;

const configs = ref<ExternalApiConfig[]>([]);
const sceneBindings = ref<ExternalApiSceneBinding[]>([]);
const loading = ref(false);
const secretSaving = ref(false);
const saving = ref(false);
const testing = ref(false);
const bindingSavingKey = ref("");
const bindingCreating = ref(false);
const sceneMetaSaving = ref(false);
const modalOpen = ref(false);
const sceneModalOpen = ref(false);
const sceneMetaModalOpen = ref(false);
const editingId = ref<number | null>(null);
const sceneEditingKey = ref("");
const isCopyMode = ref(false);
const isSceneCopyMode = ref(false);
const configGroupFilter = ref("all");
const configRequestFormatFilter = ref<"all" | ExternalApiRequestFormat>("all");
const configNameFilter = ref("");
const bindingGroupFilter = ref("all");
const bindingSceneTypeFilter = ref<"all" | ExternalApiSceneType>("all");
const bindingNameFilter = ref("");
const secretVisible = ref(false);
const tongyiSecretVisible = ref(false);
const geminiKey = ref("");
const tongyiKey = ref("");
const configImportJson = ref("");
const sceneImportJson = ref("");

const configColumns = [
  { title: "名称", dataIndex: "name", width: 280 },
  { title: "分组", dataIndex: "group_name", width: 100 },
  { title: "请求格式", dataIndex: "request_format", width: 120 },
  { title: "请求地址", dataIndex: "request_url", ellipsis: true },
  { title: "状态", dataIndex: "status", width: 100 },
  { title: "更新时间", dataIndex: "updated_at", width: 180 },
  { title: "操作", key: "action", width: 460 },
];

const bindingColumns = [
  { title: "调用场景", key: "scene", width: 220 },
  { title: "显示文案", key: "copy", width: 320 },
  { title: "当前绑定接口", key: "current", width: 260 },
  { title: "主接口", key: "bind", width: 320 },
  { title: "备用接口", key: "backup", width: 320 },
  { title: "消耗积分", key: "credit", width: 180 },
  { title: "操作", key: "action", width: 420 },
];

const form = reactive<ExternalApiConfigPayload>({
  name: "",
  description: "",
  group_name: "默认",
  request_url: "",
  request_format: "json",
  headers_json: '{\n  "Content-Type": "application/json"\n}',
  payload_json: "{\n\n}",
  response_json: "{\n\n}",
  result_base64_field: "candidates.0.content.parts.0.inlineData.data",
  status: "enabled",
});
const sceneForm = reactive<ExternalApiSceneBindingCreatePayload>({
  scene_key: "",
  scene_type: "generate",
  scene_label: "",
  scene_description: "",
  sort_order: 100,
  hide_aspect_ratio: false,
  hide_resolution: false,
  hide_custom_size: true,
  api_config_id: null,
  backup_api_config_id: null,
  display_name: "",
  subtitle: "",
  credit_cost: 4,
  max_reference_images: 0,
  aspect_ratio_options_json: DEFAULT_ASPECT_RATIO_OPTIONS_JSON,
  image_size_options_json: DEFAULT_IMAGE_SIZE_OPTIONS_JSON,
  custom_size_options_json: DEFAULT_CUSTOM_SIZE_OPTIONS_JSON,
  resolution_mapping_json: DEFAULT_RESOLUTION_MAPPING_JSON,
  resolution_credit_costs_json: DEFAULT_RESOLUTION_CREDIT_COSTS_JSON,
});
const sceneMetaForm = reactive<ExternalApiSceneBindingMetaPayload>({
  scene_key: "",
  scene_label: "",
  scene_description: "",
  sort_order: 0,
  hide_aspect_ratio: false,
  hide_resolution: false,
  hide_custom_size: true,
  max_reference_images: 0,
  aspect_ratio_options_json: DEFAULT_ASPECT_RATIO_OPTIONS_JSON,
  image_size_options_json: DEFAULT_IMAGE_SIZE_OPTIONS_JSON,
  custom_size_options_json: DEFAULT_CUSTOM_SIZE_OPTIONS_JSON,
  resolution_mapping_json: DEFAULT_RESOLUTION_MAPPING_JSON,
  resolution_credit_costs_json: DEFAULT_RESOLUTION_CREDIT_COSTS_JSON,
});

const modalTitle = computed(() => {
  if (editingId.value) return "编辑接口配置";
  if (isCopyMode.value) return "复制新增接口配置";
  return "新增接口配置";
});
const sceneModalTitle = computed(() => (isSceneCopyMode.value ? "复制新增场景" : "新增场景"));
const groupOptions = computed(() => {
  const groups = Array.from(new Set(configs.value.map((item) => item.group_name || "未分组").filter(Boolean)));
  return groups.sort((a, b) => a.localeCompare(b, "zh-CN"));
});
const filteredConfigs = computed(() => configs.value.filter((item) => {
  if (configGroupFilter.value !== "all" && item.group_name !== configGroupFilter.value) return false;
  if (configRequestFormatFilter.value !== "all" && item.request_format !== configRequestFormatFilter.value) return false;
  if (!matchesNameFilter(configNameFilter.value, item.name, item.description)) return false;
  return true;
}));
const filteredSceneBindings = computed(() => sceneBindings.value.filter((item) => {
  if (bindingGroupFilter.value !== "all" && (item.api_group_name || "未分组") !== bindingGroupFilter.value) return false;
  if (bindingSceneTypeFilter.value !== "all" && item.scene_type !== bindingSceneTypeFilter.value) return false;
  if (!matchesNameFilter(
    bindingNameFilter.value,
    item.scene_label,
    item.scene_key,
    item.display_name,
    item.scene_description,
    item.api_config_name,
  )) return false;
  return true;
}));
const maskedGeminiKey = computed(() => {
  if (!geminiKey.value) return "";
  const value = geminiKey.value;
  if (value.length <= 8) return "••••••••";
  return value.slice(0, 4) + "••••••••" + value.slice(-4);
});
const maskedTongyiKey = computed(() => {
  if (!tongyiKey.value) return "";
  const value = tongyiKey.value;
  if (value.length <= 8) return "••••••••";
  return value.slice(0, 4) + "••••••••" + value.slice(-4);
});

function sceneTypeLabel(sceneType: ExternalApiSceneBinding["scene_type"]) {
  if (sceneType === "generate") return "文生图";
  if (sceneType === "image_edit") return "图编辑";
  if (sceneType === "inpaint") return "局部重绘";
  if (sceneType === "prompt_reverse") return "提示词反推";
  if (sceneType === "prompt_optimize") return "提示词优化";
  return sceneType;
}

function requestFormatLabel(requestFormat: ExternalApiConfig["request_format"]) {
  return requestFormat === "multipart" ? "Multipart Form" : "JSON";
}

function matchesNameFilter(keyword: string, ...fields: Array<string | null | undefined>) {
  const normalized = keyword.trim().toLowerCase();
  if (!normalized) return true;
  return fields.some((field) => (field || "").toLowerCase().includes(normalized));
}

function normalizeStringValue(value: unknown, fallback = "") {
  return typeof value === "string" ? value : (value == null ? fallback : String(value));
}

function normalizeNumberValue(value: unknown, fallback = 0) {
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : fallback;
}

function normalizeBooleanValue(value: unknown, fallback = false) {
  return typeof value === "boolean" ? value : fallback;
}

function normalizeNullableNumberValue(value: unknown) {
  if (value == null || value === "") return null;
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : null;
}

function normalizeJsonFieldValue(value: unknown, fallback: string) {
  if (typeof value === "string" && value.trim()) return value;
  if (value && typeof value === "object") return JSON.stringify(value, null, 2);
  return fallback;
}

function resetForm() {
  editingId.value = null;
  isCopyMode.value = false;
  configImportJson.value = "";
  form.name = "";
  form.description = "";
  form.group_name = "默认";
  form.request_url = "";
  form.request_format = "json";
  form.headers_json = '{\n  "Content-Type": "application/json"\n}';
  form.payload_json = "{\n\n}";
  form.response_json = "{\n\n}";
  form.result_base64_field = "candidates.0.content.parts.0.inlineData.data";
  form.status = "enabled";
}

function fillForm(item: ExternalApiConfig) {
  editingId.value = item.id;
  isCopyMode.value = false;
  configImportJson.value = "";
  form.name = item.name;
  form.description = item.description || "";
  form.group_name = item.group_name || "默认";
  form.request_url = item.request_url;
  form.request_format = item.request_format || "json";
  form.headers_json = item.headers_json;
  form.payload_json = item.payload_json;
  form.response_json = item.response_json || "{\n\n}";
  form.result_base64_field = item.result_base64_field || "";
  form.status = item.status;
}

function buildCopiedName(sourceName: string) {
  const trimmed = sourceName.trim() || "未命名接口";
  const existingNames = new Set(configs.value.map((item) => item.name.trim()));
  const baseName = `${trimmed}（副本）`;
  if (!existingNames.has(baseName)) return baseName;

  let index = 2;
  while (existingNames.has(`${trimmed}（副本${index}）`)) {
    index += 1;
  }
  return `${trimmed}（副本${index}）`;
}

function getBindingOptions() {
  return configs.value
    .filter((item) => item.status === "enabled")
    .filter((item) => bindingGroupFilter.value === "all" || item.group_name === bindingGroupFilter.value)
    .map((item) => ({
      label: `${item.name}${item.group_name ? ` (${item.group_name})` : ""}`,
      value: item.id,
    }));
}

function resetSceneForm() {
  isSceneCopyMode.value = false;
  sceneImportJson.value = "";
  sceneForm.scene_key = "";
  sceneForm.scene_type = "generate";
  sceneForm.scene_label = "";
  sceneForm.scene_description = "";
  sceneForm.sort_order = Math.max(100, ...sceneBindings.value.map((item) => Number(item.sort_order || 0) + 10), 100);
  sceneForm.hide_aspect_ratio = false;
  sceneForm.hide_resolution = false;
  sceneForm.hide_custom_size = true;
  sceneForm.api_config_id = null;
  sceneForm.backup_api_config_id = null;
  sceneForm.display_name = "";
  sceneForm.subtitle = "";
  sceneForm.credit_cost = 4;
  sceneForm.max_reference_images = 0;
  sceneForm.aspect_ratio_options_json = DEFAULT_ASPECT_RATIO_OPTIONS_JSON;
  sceneForm.image_size_options_json = DEFAULT_IMAGE_SIZE_OPTIONS_JSON;
  sceneForm.custom_size_options_json = DEFAULT_CUSTOM_SIZE_OPTIONS_JSON;
  sceneForm.resolution_mapping_json = DEFAULT_RESOLUTION_MAPPING_JSON;
  sceneForm.resolution_credit_costs_json = DEFAULT_RESOLUTION_CREDIT_COSTS_JSON;
}

function buildCopiedSceneLabel(sourceLabel: string) {
  const trimmed = sourceLabel.trim() || "未命名场景";
  const existingLabels = new Set(sceneBindings.value.map((item) => item.scene_label.trim()));
  const baseLabel = `${trimmed}（副本）`;
  if (!existingLabels.has(baseLabel)) return baseLabel;

  let index = 2;
  while (existingLabels.has(`${trimmed}（副本${index}）`)) {
    index += 1;
  }
  return `${trimmed}（副本${index}）`;
}

function buildCopiedSceneKey(sourceKey: string) {
  const normalized = sourceKey.trim().toLowerCase() || "scene";
  const existingKeys = new Set(sceneBindings.value.map((item) => item.scene_key.trim().toLowerCase()));
  const baseKey = `${normalized}_copy`;
  if (!existingKeys.has(baseKey)) return baseKey;

  let index = 2;
  while (existingKeys.has(`${normalized}_copy_${index}`)) {
    index += 1;
  }
  return `${normalized}_copy_${index}`;
}

function isCopyableSceneType(
  sceneType: ExternalApiSceneType
): sceneType is Extract<ExternalApiSceneType, "generate" | "image_edit"> {
  return sceneType === "generate" || sceneType === "image_edit";
}

function canCopyScene(record: ExternalApiSceneBinding) {
  return isCopyableSceneType(record.scene_type);
}

function fillSceneMetaForm(record: ExternalApiSceneBinding) {
  sceneEditingKey.value = record.scene_key;
  sceneImportJson.value = "";
  sceneMetaForm.scene_key = record.scene_key;
  sceneMetaForm.scene_label = record.scene_label || "";
  sceneMetaForm.scene_description = record.scene_description || "";
  sceneMetaForm.sort_order = Number(record.sort_order || 0);
  sceneMetaForm.hide_aspect_ratio = !!record.hide_aspect_ratio;
  sceneMetaForm.hide_resolution = !!record.hide_resolution;
  sceneMetaForm.hide_custom_size = !!record.hide_custom_size;
  sceneMetaForm.max_reference_images = Number(record.max_reference_images || 0);
  sceneMetaForm.aspect_ratio_options_json = record.aspect_ratio_options_json || DEFAULT_ASPECT_RATIO_OPTIONS_JSON;
  sceneMetaForm.image_size_options_json = record.image_size_options_json || DEFAULT_IMAGE_SIZE_OPTIONS_JSON;
  sceneMetaForm.custom_size_options_json = record.custom_size_options_json || DEFAULT_CUSTOM_SIZE_OPTIONS_JSON;
  sceneMetaForm.resolution_mapping_json = record.resolution_mapping_json || DEFAULT_RESOLUTION_MAPPING_JSON;
  sceneMetaForm.resolution_credit_costs_json = record.resolution_credit_costs_json || DEFAULT_RESOLUTION_CREDIT_COSTS_JSON;
}

watch(
  () => sceneForm.scene_type,
  (sceneType, previousType) => {
    if (sceneType === previousType) return;
    if (sceneType === "image_edit" && Number(sceneForm.max_reference_images || 0) <= 0) {
      sceneForm.max_reference_images = DEFAULT_IMAGE_EDIT_MAX_REFERENCE_IMAGES;
    }
    if (sceneType === "generate" && Number(sceneForm.max_reference_images || 0) === DEFAULT_IMAGE_EDIT_MAX_REFERENCE_IMAGES) {
      sceneForm.max_reference_images = 0;
    }
  }
);

function validateSceneOptionsJson(raw: string, label: string) {
  try {
    const parsed = JSON.parse(raw || "[]");
    if (!Array.isArray(parsed)) {
      message.warning(`${label}必须是 JSON 数组`);
      return false;
    }
    for (const [index, item] of parsed.entries()) {
      if (!item || typeof item !== "object" || Array.isArray(item)) {
        message.warning(`${label}第 ${index + 1} 项必须是对象`);
        return false;
      }
      const optionLabel = String((item as Record<string, unknown>).label ?? "").trim();
      const optionValue = String((item as Record<string, unknown>).value ?? "").trim();
      if (!optionLabel || !optionValue) {
        message.warning(`${label}第 ${index + 1} 项必须包含非空 label 和 value`);
        return false;
      }
    }
    return true;
  } catch {
    message.warning(`${label}不是合法的 JSON`);
    return false;
  }
}

function validateResolutionMappingJson(raw: string, label: string) {
  try {
    const parsed = JSON.parse(raw || "{}");
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      message.warning(`${label}必须是 JSON 对象`);
      return false;
    }
    for (const [aspectRatio, resolutionMap] of Object.entries(parsed as Record<string, unknown>)) {
      if (!String(aspectRatio).trim()) {
        message.warning(`${label}的宽高比键不能为空`);
        return false;
      }
      if (!resolutionMap || Array.isArray(resolutionMap) || typeof resolutionMap !== "object") {
        message.warning(`${label}中 ${aspectRatio} 的值必须是对象`);
        return false;
      }
      for (const [imageSize, mappedResolution] of Object.entries(resolutionMap as Record<string, unknown>)) {
        if (!String(imageSize).trim() || !String(mappedResolution ?? "").trim()) {
          message.warning(`${label}中 ${aspectRatio} 的分辨率键和值不能为空`);
          return false;
        }
      }
    }
    return true;
  } catch {
    message.warning(`${label}不是合法的 JSON`);
    return false;
  }
}

function validateResolutionCreditCostsJson(raw: string, label: string) {
  try {
    const parsed = JSON.parse(raw || "{}");
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      message.warning(`${label}必须是 JSON 对象`);
      return false;
    }
    for (const [resolution, creditCost] of Object.entries(parsed as Record<string, unknown>)) {
      if (!String(resolution).trim()) {
        message.warning(`${label}的分辨率键不能为空`);
        return false;
      }
      if (typeof creditCost === "boolean" || !Number.isInteger(Number(creditCost))) {
        message.warning(`${label}中 ${resolution} 的积分消耗必须是整数`);
        return false;
      }
      if (Number(creditCost) < 0) {
        message.warning(`${label}中 ${resolution} 的积分消耗不能小于 0`);
        return false;
      }
    }
    return true;
  } catch {
    message.warning(`${label}不是合法的 JSON`);
    return false;
  }
}

async function load() {
  loading.value = true;
  try {
    const [configRows, bindingRows, secretConfig] = await Promise.all([
      listExternalApiConfigs(),
      listExternalApiSceneBindings(),
      getExternalApiSecrets(),
    ]);
    configs.value = configRows;
    sceneBindings.value = bindingRows;
    geminiKey.value = secretConfig?.key || "";
    tongyiKey.value = secretConfig?.tongyi_key || "";
  } catch (err: any) {
    message.error(err.response?.data?.detail || "获取接口管理数据失败");
  } finally {
    loading.value = false;
  }
}

onMounted(load);

function openCreate() {
  resetForm();
  modalOpen.value = true;
}

function openCreateScene() {
  resetSceneForm();
  sceneModalOpen.value = true;
}

function openCopyScene(record: ExternalApiSceneBinding) {
  if (!isCopyableSceneType(record.scene_type)) return;
  resetSceneForm();
  isSceneCopyMode.value = true;
  sceneForm.scene_key = buildCopiedSceneKey(record.scene_key);
  sceneForm.scene_type = record.scene_type;
  sceneForm.scene_label = buildCopiedSceneLabel(record.scene_label);
  sceneForm.scene_description = record.scene_description || "";
  sceneForm.sort_order = Number(record.sort_order || 0) + 10;
  sceneForm.hide_aspect_ratio = !!record.hide_aspect_ratio;
  sceneForm.hide_resolution = !!record.hide_resolution;
  sceneForm.hide_custom_size = !!record.hide_custom_size;
  sceneForm.api_config_id = record.api_config_id ?? null;
  sceneForm.backup_api_config_id = record.backup_api_config_id ?? null;
  sceneForm.display_name = record.display_name || "";
  sceneForm.subtitle = record.subtitle || "";
  sceneForm.credit_cost = Number(record.credit_cost || 0);
  sceneForm.max_reference_images = Number(record.max_reference_images || 0);
  sceneForm.aspect_ratio_options_json = record.aspect_ratio_options_json || DEFAULT_ASPECT_RATIO_OPTIONS_JSON;
  sceneForm.image_size_options_json = record.image_size_options_json || DEFAULT_IMAGE_SIZE_OPTIONS_JSON;
  sceneForm.custom_size_options_json = record.custom_size_options_json || DEFAULT_CUSTOM_SIZE_OPTIONS_JSON;
  sceneForm.resolution_mapping_json = record.resolution_mapping_json || DEFAULT_RESOLUTION_MAPPING_JSON;
  sceneForm.resolution_credit_costs_json = record.resolution_credit_costs_json || DEFAULT_RESOLUTION_CREDIT_COSTS_JSON;
  sceneModalOpen.value = true;
}

function openEditSceneMeta(record: ExternalApiSceneBinding) {
  fillSceneMetaForm(record);
  sceneMetaModalOpen.value = true;
}

function openEdit(item: ExternalApiConfig) {
  fillForm(item);
  modalOpen.value = true;
}

function openCopy(item: ExternalApiConfig) {
  resetForm();
  isCopyMode.value = true;
  form.name = buildCopiedName(item.name);
  form.description = item.description || "";
  form.group_name = item.group_name || "默认";
  form.request_url = item.request_url;
  form.request_format = item.request_format || "json";
  form.headers_json = item.headers_json;
  form.payload_json = item.payload_json;
  form.response_json = item.response_json || "{\n\n}";
  form.result_base64_field = item.result_base64_field || "";
  form.status = item.status;
  modalOpen.value = true;
}

function buildConfigTemplateData(item: ExternalApiConfig): ExternalApiConfigPayload {
  return {
    name: item.name,
    description: item.description || "",
    group_name: item.group_name || "默认",
    request_url: item.request_url,
    request_format: item.request_format || "json",
    headers_json: item.headers_json,
    payload_json: item.payload_json,
    response_json: item.response_json || "{\n\n}",
    result_base64_field: item.result_base64_field || "",
    status: item.status,
  };
}

function buildSceneTemplateData(record: ExternalApiSceneBinding): ExternalApiSceneBindingCreatePayload {
  if (!isCopyableSceneType(record.scene_type)) {
    throw new Error("当前场景类型暂不支持导出为新增模板");
  }
  return {
    scene_key: record.scene_key,
    scene_type: record.scene_type,
    scene_label: record.scene_label,
    scene_description: record.scene_description || "",
    sort_order: Number(record.sort_order || 0),
    hide_aspect_ratio: !!record.hide_aspect_ratio,
    hide_resolution: !!record.hide_resolution,
    hide_custom_size: !!record.hide_custom_size,
    api_config_id: record.api_config_id ?? null,
    backup_api_config_id: record.backup_api_config_id ?? null,
    display_name: record.display_name || "",
    subtitle: record.subtitle || "",
    credit_cost: Number(record.credit_cost || 0),
    max_reference_images: Number(record.max_reference_images || 0),
    aspect_ratio_options_json: record.aspect_ratio_options_json || DEFAULT_ASPECT_RATIO_OPTIONS_JSON,
    image_size_options_json: record.image_size_options_json || DEFAULT_IMAGE_SIZE_OPTIONS_JSON,
    custom_size_options_json: record.custom_size_options_json || DEFAULT_CUSTOM_SIZE_OPTIONS_JSON,
    resolution_mapping_json: record.resolution_mapping_json || DEFAULT_RESOLUTION_MAPPING_JSON,
    resolution_credit_costs_json: record.resolution_credit_costs_json || DEFAULT_RESOLUTION_CREDIT_COSTS_JSON,
  };
}

async function copyTemplateJson(text: string, successMessage: string) {
  try {
    await navigator.clipboard.writeText(text);
    message.success(successMessage);
  } catch {
    message.error("复制失败，请检查剪贴板权限");
  }
}

function handleCopyConfigJson(item: ExternalApiConfig) {
  const template = stringifyAdminConfigTemplate("image-api-config", buildConfigTemplateData(item));
  void copyTemplateJson(template, "接口配置 JSON 已复制");
}

function handleCopySceneJson(record: ExternalApiSceneBinding) {
  const template = stringifyAdminConfigTemplate("image-scene-binding", buildSceneTemplateData(record));
  void copyTemplateJson(template, "场景绑定 JSON 已复制");
}

function applyImportedConfigData(data: Record<string, unknown>) {
  form.name = normalizeStringValue(data.name, form.name);
  form.description = normalizeStringValue(data.description, form.description);
  form.group_name = normalizeStringValue(data.group_name, form.group_name || "默认");
  form.request_url = normalizeStringValue(data.request_url, form.request_url);
  form.request_format = data.request_format === "multipart" ? "multipart" : "json";
  form.headers_json = normalizeJsonFieldValue(data.headers_json, form.headers_json);
  form.payload_json = normalizeJsonFieldValue(data.payload_json, form.payload_json);
  form.response_json = normalizeJsonFieldValue(data.response_json, form.response_json);
  form.result_base64_field = normalizeStringValue(data.result_base64_field, form.result_base64_field);
  form.status = data.status === "disabled" ? "disabled" : "enabled";
}

function handleApplyConfigImportJson() {
  if (!configImportJson.value.trim()) {
    message.warning("请先粘贴接口配置 JSON");
    return;
  }
  try {
    const parsed = parseAdminConfigTemplate(configImportJson.value);
    if (parsed.kind !== "image-api-config") {
      message.warning("这段 JSON 不是图片接口配置模板");
      return;
    }
    applyImportedConfigData(parsed.data);
    message.success("已识别并回填接口配置");
  } catch (err: any) {
    message.error(err?.message || "识别接口配置 JSON 失败");
  }
}

function applyImportedSceneData(data: Record<string, unknown>) {
  sceneForm.scene_key = normalizeStringValue(data.scene_key, sceneForm.scene_key);
  sceneForm.scene_type = data.scene_type === "image_edit" ? "image_edit" : "generate";
  sceneForm.scene_label = normalizeStringValue(data.scene_label, sceneForm.scene_label);
  sceneForm.scene_description = normalizeStringValue(data.scene_description, sceneForm.scene_description);
  sceneForm.sort_order = normalizeNumberValue(data.sort_order, sceneForm.sort_order);
  sceneForm.hide_aspect_ratio = normalizeBooleanValue(data.hide_aspect_ratio, sceneForm.hide_aspect_ratio);
  sceneForm.hide_resolution = normalizeBooleanValue(data.hide_resolution, sceneForm.hide_resolution);
  sceneForm.hide_custom_size = normalizeBooleanValue(data.hide_custom_size, sceneForm.hide_custom_size);
  sceneForm.api_config_id = normalizeNullableNumberValue(data.api_config_id);
  sceneForm.backup_api_config_id = normalizeNullableNumberValue(data.backup_api_config_id);
  sceneForm.display_name = normalizeStringValue(data.display_name, sceneForm.display_name);
  sceneForm.subtitle = normalizeStringValue(data.subtitle, sceneForm.subtitle);
  sceneForm.credit_cost = normalizeNumberValue(data.credit_cost, sceneForm.credit_cost);
  sceneForm.max_reference_images = normalizeNumberValue(data.max_reference_images, sceneForm.max_reference_images);
  sceneForm.aspect_ratio_options_json = normalizeJsonFieldValue(data.aspect_ratio_options_json, sceneForm.aspect_ratio_options_json);
  sceneForm.image_size_options_json = normalizeJsonFieldValue(data.image_size_options_json, sceneForm.image_size_options_json);
  sceneForm.custom_size_options_json = normalizeJsonFieldValue(data.custom_size_options_json, sceneForm.custom_size_options_json);
  sceneForm.resolution_mapping_json = normalizeJsonFieldValue(data.resolution_mapping_json, sceneForm.resolution_mapping_json);
  sceneForm.resolution_credit_costs_json = normalizeJsonFieldValue(data.resolution_credit_costs_json, sceneForm.resolution_credit_costs_json);
}

function handleApplySceneImportJson() {
  if (!sceneImportJson.value.trim()) {
    message.warning("请先粘贴场景绑定 JSON");
    return;
  }
  try {
    const parsed = parseAdminConfigTemplate(sceneImportJson.value);
    if (parsed.kind !== "image-scene-binding") {
      message.warning("这段 JSON 不是图片场景绑定模板");
      return;
    }
    applyImportedSceneData(parsed.data);
    message.success("已识别并回填场景绑定");
  } catch (err: any) {
    message.error(err?.message || "识别场景绑定 JSON 失败");
  }
}

function validateJsonFields() {
  try {
    const headers = JSON.parse(form.headers_json);
    if (!headers || Array.isArray(headers) || typeof headers !== "object") {
      message.warning("Header JSON 必须是对象");
      return false;
    }
  } catch {
    message.warning("Header JSON 不是合法的 JSON");
    return false;
  }

  try {
    JSON.parse(form.payload_json);
  } catch {
    message.warning("请求 JSON 不是合法的 JSON");
    return false;
  }

  try {
    JSON.parse(form.response_json);
  } catch {
    message.warning("响应 JSON 不是合法的 JSON");
    return false;
  }

  return true;
}

function buildPayload(): ExternalApiConfigPayload {
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    group_name: form.group_name.trim() || "默认",
    request_url: form.request_url.trim(),
    request_format: form.request_format,
    headers_json: form.headers_json,
    payload_json: form.payload_json,
    response_json: form.response_json,
    result_base64_field: form.result_base64_field.trim(),
    status: form.status,
  };
}

async function handleSave() {
  if (!form.name.trim()) {
    message.warning("请输入配置名称");
    return;
  }
  if (!form.request_url.trim()) {
    message.warning("请输入请求地址");
    return;
  }
  if (!validateJsonFields()) return;

  saving.value = true;
  try {
    const payload = buildPayload();
    if (editingId.value) {
      await updateExternalApiConfig(editingId.value, payload);
      message.success("接口配置更新成功");
    } else {
      await createExternalApiConfig(payload);
      message.success("接口配置创建成功");
    }
    modalOpen.value = false;
    resetForm();
    await load();
  } catch (err: any) {
    message.error(err.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

async function handleTestConnection() {
  if (!form.name.trim()) {
    message.warning("请先填写配置名称");
    return;
  }
  if (!form.request_url.trim()) {
    message.warning("请先填写请求地址");
    return;
  }
  if (!validateJsonFields()) return;

  testing.value = true;
  try {
    const result = await testExternalApiConfig(buildPayload());
    showTestResult(result);
  } catch (err: any) {
    message.error(err.response?.data?.detail || "测试连接失败");
  } finally {
    testing.value = false;
  }
}

function showTestResult(result: ExternalApiConfigTestResult) {
  Modal.info({
    title: result.success ? "测试连接成功" : "测试连接失败",
    width: 760,
    centered: true,
    okText: "知道了",
    content: [
      `请求地址：${result.request_url}`,
      `状态码：${result.status_code ?? "-"}`,
      "",
      "响应摘要：",
      result.response_preview || "(空响应)",
    ].join("\n"),
  });
}

function handleToggleStatus(item: ExternalApiConfig) {
  const nextStatus = item.status === "enabled" ? "disabled" : "enabled";
  Modal.confirm({
    title: nextStatus === "enabled" ? "启用该接口配置？" : "停用该接口配置？",
    centered: true,
    onOk: async () => {
      try {
        await updateExternalApiConfigStatus(item.id, nextStatus);
        message.success(nextStatus === "enabled" ? "已启用" : "已停用");
        await load();
      } catch (err: any) {
        message.error(err.response?.data?.detail || "更新状态失败");
      }
    },
  });
}

function handleDeleteConfig(item: ExternalApiConfig) {
  Modal.confirm({
    title: "删除该接口配置？",
    content: "删除后会同时解除所有引用它的场景绑定，场景会保留但变成未绑定状态。",
    centered: true,
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await deleteExternalApiConfig(item.id);
        message.success("接口配置已删除");
        await load();
      } catch (err: any) {
        message.error(err.response?.data?.detail || "删除接口配置失败");
      }
    },
  });
}

async function handleBindingChange(
  sceneKey: ExternalApiSceneBinding["scene_key"],
  payload: {
    api_config_id: number | null;
    backup_api_config_id: number | null;
    credit_cost: number;
    resolution_credit_costs_json: string;
    display_name: string;
    subtitle: string;
  },
) {
  bindingSavingKey.value = sceneKey;
  try {
    await updateExternalApiSceneBinding(sceneKey, payload);
    message.success("场景绑定已更新");
    await load();
  } catch (err: any) {
    message.error(err.response?.data?.detail || "更新绑定失败");
  } finally {
    bindingSavingKey.value = "";
  }
}

function buildBindingPayload(record: ExternalApiSceneBinding, overrides: Partial<{
  api_config_id: number | null;
  backup_api_config_id: number | null;
  credit_cost: number;
  resolution_credit_costs_json: string;
  display_name: string;
  subtitle: string;
}> = {}) {
  return {
    api_config_id: overrides.api_config_id ?? record.api_config_id ?? null,
    backup_api_config_id: overrides.backup_api_config_id ?? record.backup_api_config_id ?? null,
    credit_cost: overrides.credit_cost ?? record.credit_cost,
    resolution_credit_costs_json: overrides.resolution_credit_costs_json ?? record.resolution_credit_costs_json ?? DEFAULT_RESOLUTION_CREDIT_COSTS_JSON,
    display_name: overrides.display_name ?? record.display_name ?? "",
    subtitle: overrides.subtitle ?? record.subtitle ?? "",
  };
}

async function handleCreateScene() {
  if (!sceneForm.scene_key.trim()) {
    message.warning("请输入场景标识");
    return;
  }
  if (!sceneForm.scene_label.trim()) {
    message.warning("请输入场景名称");
    return;
  }
  if (!validateSceneOptionsJson(sceneForm.aspect_ratio_options_json, "宽高比选项 JSON")) return;
  if (!validateSceneOptionsJson(sceneForm.image_size_options_json, "生图质量选项 JSON")) return;
  if (!validateSceneOptionsJson(sceneForm.custom_size_options_json, "自定义分辨率选项 JSON")) return;
  if (!validateResolutionMappingJson(sceneForm.resolution_mapping_json, "分辨率映射 JSON")) return;
  if (!validateResolutionCreditCostsJson(sceneForm.resolution_credit_costs_json, "分辨率积分 JSON")) return;

  bindingCreating.value = true;
  try {
    await createExternalApiSceneBinding({
      scene_key: sceneForm.scene_key.trim().toLowerCase(),
      scene_type: sceneForm.scene_type,
      scene_label: sceneForm.scene_label.trim(),
      scene_description: sceneForm.scene_description.trim(),
      sort_order: Number(sceneForm.sort_order || 0),
      hide_aspect_ratio: !!sceneForm.hide_aspect_ratio,
      hide_resolution: !!sceneForm.hide_resolution,
      hide_custom_size: !!sceneForm.hide_custom_size,
      api_config_id: sceneForm.api_config_id ?? null,
      backup_api_config_id: sceneForm.backup_api_config_id ?? null,
      display_name: sceneForm.display_name.trim(),
      subtitle: sceneForm.subtitle.trim(),
      credit_cost: Number(sceneForm.credit_cost || 0),
      max_reference_images: Number(sceneForm.max_reference_images || 0),
      aspect_ratio_options_json: sceneForm.aspect_ratio_options_json,
      image_size_options_json: sceneForm.image_size_options_json,
      custom_size_options_json: sceneForm.custom_size_options_json,
      resolution_mapping_json: sceneForm.resolution_mapping_json,
      resolution_credit_costs_json: sceneForm.resolution_credit_costs_json,
    });
    message.success("场景创建成功");
    sceneModalOpen.value = false;
    resetSceneForm();
    await load();
  } catch (err: any) {
    message.error(err.response?.data?.detail || "创建场景失败");
  } finally {
    bindingCreating.value = false;
  }
}

async function handleSaveSceneMeta() {
  if (!sceneEditingKey.value) return;
  if (!sceneMetaForm.scene_key.trim()) {
    message.warning("请输入场景标识");
    return;
  }
  if (!sceneMetaForm.scene_label.trim()) {
    message.warning("请输入场景名称");
    return;
  }
  if (!validateSceneOptionsJson(sceneMetaForm.aspect_ratio_options_json, "宽高比选项 JSON")) return;
  if (!validateSceneOptionsJson(sceneMetaForm.image_size_options_json, "生图质量选项 JSON")) return;
  if (!validateSceneOptionsJson(sceneMetaForm.custom_size_options_json, "自定义分辨率选项 JSON")) return;
  if (!validateResolutionMappingJson(sceneMetaForm.resolution_mapping_json, "分辨率映射 JSON")) return;
  if (!validateResolutionCreditCostsJson(sceneMetaForm.resolution_credit_costs_json, "分辨率积分 JSON")) return;

  sceneMetaSaving.value = true;
  try {
    await updateExternalApiSceneBindingMeta(sceneEditingKey.value, {
      scene_key: sceneMetaForm.scene_key.trim().toLowerCase(),
      scene_label: sceneMetaForm.scene_label.trim(),
      scene_description: sceneMetaForm.scene_description.trim(),
      sort_order: Number(sceneMetaForm.sort_order || 0),
      hide_aspect_ratio: !!sceneMetaForm.hide_aspect_ratio,
      hide_resolution: !!sceneMetaForm.hide_resolution,
      hide_custom_size: !!sceneMetaForm.hide_custom_size,
      max_reference_images: Number(sceneMetaForm.max_reference_images || 0),
      aspect_ratio_options_json: sceneMetaForm.aspect_ratio_options_json,
      image_size_options_json: sceneMetaForm.image_size_options_json,
      custom_size_options_json: sceneMetaForm.custom_size_options_json,
      resolution_mapping_json: sceneMetaForm.resolution_mapping_json,
      resolution_credit_costs_json: sceneMetaForm.resolution_credit_costs_json,
    });
    message.success("场景基础信息已更新");
    sceneMetaModalOpen.value = false;
    sceneEditingKey.value = "";
    await load();
  } catch (err: any) {
    message.error(err.response?.data?.detail || "更新场景失败");
  } finally {
    sceneMetaSaving.value = false;
  }
}

function handleToggleSceneStatus(record: ExternalApiSceneBinding) {
  const nextStatus = record.status === "enabled" ? "disabled" : "enabled";
  Modal.confirm({
    title: nextStatus === "enabled" ? "启用该自定义场景？" : "停用该自定义场景？",
    centered: true,
    onOk: async () => {
      try {
        await updateExternalApiSceneBindingStatus(record.scene_key, nextStatus);
        message.success(nextStatus === "enabled" ? "场景已启用" : "场景已停用");
        await load();
      } catch (err: any) {
        message.error(err.response?.data?.detail || "更新场景状态失败");
      }
    },
  });
}

function handleDeleteScene(record: ExternalApiSceneBinding) {
  Modal.confirm({
    title: "删除该自定义场景？",
    content: "删除后将不再出现在模型选择中，且无法恢复。",
    centered: true,
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        await deleteExternalApiSceneBinding(record.scene_key);
        message.success("场景已删除");
        await load();
      } catch (err: any) {
        message.error(err.response?.data?.detail || "删除场景失败");
      }
    },
  });
}

async function handleSaveSecrets() {
  secretSaving.value = true;
  try {
    await setExternalApiSecrets({
      key: geminiKey.value.trim(),
      tongyi_key: tongyiKey.value.trim(),
    });
    message.success("接口密钥保存成功");
    await load();
  } catch (err: any) {
    message.error(err.response?.data?.detail || "接口密钥保存失败");
  } finally {
    secretSaving.value = false;
  }
}

function copySecret(value: string, label: string) {
  if (!value) return;
  navigator.clipboard.writeText(value).then(() => {
    message.success(`${label}已复制到剪贴板`);
  });
}
</script>

<template>
  <div class="page warm-page motion-page-enter">
    <a-space direction="vertical" :size="16" style="width: 100%">
      <a-card title="接口密钥" class="warm-card api-card motion-fade-up motion-card-lift" style="--motion-delay: 40ms" :loading="loading">
        <a-alert
          class="warm-alert"
          type="info"
          show-icon
          message="Gemini API Key 与通义千问 API Key 仅超级管理员可见，可在接口模板中通过 {{ api_key }} 和 {{ bearer_token }} 占位符使用。"
          style="margin-bottom: 16px"
        />
        <div class="secret-grid">
          <div>
            <div class="secret-label">Gemini API Key</div>
            <div class="secret-input-row">
              <a-input
                v-if="secretVisible"
                v-model:value="geminiKey"
                class="warm-input"
                placeholder="请输入 Gemini API Key"
              />
              <div v-else class="secret-masked" @click="secretVisible = true">
                {{ geminiKey ? maskedGeminiKey : "暂未配置" }}
              </div>
              <a-button class="api-secondary-btn api-icon-btn" @click="secretVisible = !secretVisible">
                <template #icon>
                  <EyeInvisibleOutlined v-if="secretVisible" />
                  <EyeOutlined v-else />
                </template>
              </a-button>
              <a-button class="api-secondary-btn api-icon-btn" :disabled="!geminiKey" @click="copySecret(geminiKey, 'Gemini Key')">
                <template #icon><CopyOutlined /></template>
              </a-button>
            </div>
          </div>
          <div>
            <div class="secret-label">通义千问 API Key</div>
            <div class="secret-input-row">
              <a-input
                v-if="tongyiSecretVisible"
                v-model:value="tongyiKey"
                class="warm-input"
                placeholder="请输入通义千问 API Key"
              />
              <div v-else class="secret-masked" @click="tongyiSecretVisible = true">
                {{ tongyiKey ? maskedTongyiKey : "暂未配置" }}
              </div>
              <a-button class="api-secondary-btn api-icon-btn" @click="tongyiSecretVisible = !tongyiSecretVisible">
                <template #icon>
                  <EyeInvisibleOutlined v-if="tongyiSecretVisible" />
                  <EyeOutlined v-else />
                </template>
              </a-button>
              <a-button class="api-secondary-btn api-icon-btn" :disabled="!tongyiKey" @click="copySecret(tongyiKey, '通义 Key')">
                <template #icon><CopyOutlined /></template>
              </a-button>
            </div>
          </div>
        </div>
        <a-button type="primary" class="api-primary-btn" :icon="h(SaveOutlined)" :loading="secretSaving" @click="handleSaveSecrets">
          保存接口密钥
        </a-button>
      </a-card>

      <a-card title="接口配置" class="warm-card warm-table-card api-card motion-fade-up motion-card-lift" style="--motion-delay: 120ms">
        <template #extra>
          <a-space wrap>
            <a-input
              v-model:value="configNameFilter"
              class="warm-input"
              allow-clear
              placeholder="按名称筛选"
              style="width: 180px"
            />
            <a-select
              v-model:value="configGroupFilter"
              class="warm-select"
              show-search
              option-filter-prop="label"
              placeholder="筛选分组"
              style="width: 180px"
            >
              <a-select-option value="all" label="全部分组">全部分组</a-select-option>
              <a-select-option v-for="group in groupOptions" :key="group" :value="group" :label="group">
                {{ group }}
              </a-select-option>
            </a-select>
            <a-select
              v-model:value="configRequestFormatFilter"
              class="warm-select"
              show-search
              option-filter-prop="label"
              placeholder="筛选请求格式"
              style="width: 180px"
            >
              <a-select-option value="all" label="全部格式">全部格式</a-select-option>
              <a-select-option value="json" label="JSON">JSON</a-select-option>
              <a-select-option value="multipart" label="Multipart Form">Multipart Form</a-select-option>
            </a-select>
            <a-button type="primary" class="api-primary-btn" :icon="h(PlusOutlined)" @click="openCreate">
              新增接口
            </a-button>
          </a-space>
        </template>

        <a-table
          row-key="id"
          :columns="configColumns"
          :data-source="filteredConfigs"
          :loading="loading"
          :pagination="{ pageSize: 10, class: 'warm-pagination' }"
          :scroll="{ x: 1100 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'group_name'">
              <a-tag class="api-tag api-tag-group">{{ record.group_name || "未分组" }}</a-tag>
            </template>
            <template v-else-if="column.dataIndex === 'request_format'">
              <a-tag class="api-tag" :class="record.request_format === 'multipart' ? 'api-tag-group' : 'api-tag-muted'">
                {{ requestFormatLabel(record.request_format) }}
              </a-tag>
            </template>
            <template v-else-if="column.dataIndex === 'status'">
              <a-tag class="api-tag" :class="record.status === 'enabled' ? 'api-tag-enabled' : 'api-tag-muted'">
                {{ record.status === "enabled" ? "启用" : "停用" }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-space wrap>
                <a-button size="small" class="api-secondary-btn" :icon="h(EditOutlined)" @click="openEdit(record)">编辑</a-button>
                <a-button size="small" class="api-secondary-btn" :icon="h(CopyOutlined)" @click="openCopy(record)">复制新增</a-button>
                <a-button size="small" class="api-secondary-btn" :icon="h(CopyOutlined)" @click="handleCopyConfigJson(record)">复制 JSON</a-button>
                <a-button size="small" :class="record.status === 'enabled' ? 'api-danger-btn' : 'api-secondary-btn'" @click="handleToggleStatus(record)">
                  {{ record.status === "enabled" ? "停用" : "启用" }}
                </a-button>
                <a-button size="small" class="api-danger-btn" :icon="h(DeleteOutlined)" @click="handleDeleteConfig(record)">
                  删除
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>

      <a-card title="场景绑定" class="warm-card warm-table-card api-card motion-fade-up motion-card-lift" style="--motion-delay: 200ms">
        <template #extra>
          <a-space wrap>
            <a-input
              v-model:value="bindingNameFilter"
              class="warm-input"
              allow-clear
              placeholder="按名称筛选"
              style="width: 180px"
            />
            <a-select
              v-model:value="bindingGroupFilter"
              class="warm-select"
              show-search
              option-filter-prop="label"
              placeholder="筛选分组"
              style="width: 180px"
            >
              <a-select-option value="all" label="全部分组">全部分组</a-select-option>
              <a-select-option v-for="group in groupOptions" :key="group" :value="group" :label="group">
                {{ group }}
              </a-select-option>
            </a-select>
            <a-select
              v-model:value="bindingSceneTypeFilter"
              class="warm-select"
              show-search
              option-filter-prop="label"
              placeholder="筛选场景类型"
              style="width: 180px"
            >
              <a-select-option value="all" label="全部场景">全部场景</a-select-option>
              <a-select-option value="generate" label="文生图">文生图</a-select-option>
              <a-select-option value="image_edit" label="图编辑">图编辑</a-select-option>
              <a-select-option value="prompt_reverse" label="提示词反推">提示词反推</a-select-option>
              <a-select-option value="prompt_optimize" label="提示词优化">提示词优化</a-select-option>
              <a-select-option value="inpaint" label="局部重绘">局部重绘</a-select-option>
            </a-select>
            <a-button type="primary" class="api-primary-btn" :icon="h(PlusOutlined)" @click="openCreateScene">
              新增场景
            </a-button>
          </a-space>
        </template>

        <a-alert
          class="warm-alert"
          type="info"
          show-icon
          message="可分别新增文生图或图编辑场景；新增后会出现在生成页对应 tab 的模型选择中。接口分组仅用于此处筛选。"
          style="margin-bottom: 16px"
        />

        <a-table
          row-key="scene_key"
          :columns="bindingColumns"
          :data-source="filteredSceneBindings"
          :loading="loading"
          :pagination="false"
          :scroll="{ x: 1540 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'scene'">
              <div class="scene-title">{{ record.scene_label }}</div>
              <div class="scene-desc">{{ record.scene_description }}</div>
              <a-space size="small" style="margin-top: 6px">
                <a-tag class="api-tag api-tag-group">{{ sceneTypeLabel(record.scene_type) }}</a-tag>
                <a-tag v-if="record.is_builtin" class="api-tag api-tag-muted">内置</a-tag>
                <a-tag class="api-tag" :class="record.status === 'enabled' ? 'api-tag-enabled' : 'api-tag-muted'">
                  {{ record.status === "enabled" ? "启用" : "停用" }}
                </a-tag>
              </a-space>
            </template>
            <template v-else-if="column.key === 'copy'">
              <div class="binding-copy-cell">
                <a-input
                  v-model:value="record.display_name"
                  class="warm-input"
                  placeholder="显示名称，为空则使用默认名称"
                />
                <a-input
                  v-model:value="record.subtitle"
                  class="warm-input"
                  placeholder="副标题，为空则使用默认副标题"
                />
                <a-button
                  size="small"
                  class="api-secondary-btn"
                  :loading="bindingSavingKey === record.scene_key"
                  @click="handleBindingChange(record.scene_key, buildBindingPayload(record))"
                >
                  保存文案
                </a-button>
              </div>
            </template>
            <template v-else-if="column.key === 'current'">
              <div class="binding-current-stack">
                <div>
                  <div class="scene-desc" style="margin-bottom: 4px">主接口</div>
                  <div v-if="record.api_config_name">
                    <div>{{ record.api_config_name }}</div>
                    <a-space size="small">
                      <a-tag class="api-tag api-tag-group">{{ record.api_group_name || "未分组" }}</a-tag>
                      <a-tag class="api-tag" :class="record.api_status === 'enabled' ? 'api-tag-enabled' : 'api-tag-muted'">
                        {{ record.api_status === "enabled" ? "启用" : "停用" }}
                      </a-tag>
                    </a-space>
                  </div>
                  <span v-else class="scene-desc">未绑定</span>
                </div>
                <div>
                  <div class="scene-desc" style="margin-bottom: 4px">备用接口</div>
                  <div v-if="record.backup_api_config_name">
                    <div>{{ record.backup_api_config_name }}</div>
                    <a-space size="small">
                      <a-tag class="api-tag api-tag-group">{{ record.backup_api_group_name || "未分组" }}</a-tag>
                      <a-tag class="api-tag" :class="record.backup_api_status === 'enabled' ? 'api-tag-enabled' : 'api-tag-muted'">
                        {{ record.backup_api_status === "enabled" ? "启用" : "停用" }}
                      </a-tag>
                    </a-space>
                  </div>
                  <span v-else class="scene-desc">未绑定</span>
                </div>
              </div>
            </template>
            <template v-else-if="column.key === 'bind'">
              <a-select
                :value="record.api_config_id ?? undefined"
                class="warm-select"
                allow-clear
                placeholder="请选择主接口"
                style="width: 280px"
                :loading="bindingSavingKey === record.scene_key"
                @change="(value: number | undefined) => handleBindingChange(record.scene_key, buildBindingPayload(record, { api_config_id: value ?? null }))"
              >
                <a-select-option
                  v-for="option in getBindingOptions()"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </a-select-option>
              </a-select>
            </template>
            <template v-else-if="column.key === 'backup'">
              <a-select
                :value="record.backup_api_config_id ?? undefined"
                class="warm-select"
                allow-clear
                placeholder="请选择备用接口"
                style="width: 280px"
                :loading="bindingSavingKey === record.scene_key"
                @change="(value: number | undefined) => handleBindingChange(record.scene_key, buildBindingPayload(record, { backup_api_config_id: value ?? null }))"
              >
                <a-select-option
                  v-for="option in getBindingOptions()"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </a-select-option>
              </a-select>
            </template>
            <template v-else-if="column.key === 'credit'">
              <a-input-number
                :value="record.credit_cost"
                class="warm-input-number"
                :min="0"
                :precision="0"
                :disabled="bindingSavingKey === record.scene_key"
                @change="(value: number | null) => handleBindingChange(record.scene_key, buildBindingPayload(record, { credit_cost: Number(value ?? 0) }))"
              />
              <span class="credit-unit">积分</span>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-space wrap>
                <a-button v-if="canCopyScene(record)" size="small" class="api-secondary-btn" :icon="h(CopyOutlined)" @click="openCopyScene(record)">
                  复制新增
                </a-button>
                <a-button v-if="canCopyScene(record)" size="small" class="api-secondary-btn" :icon="h(CopyOutlined)" @click="handleCopySceneJson(record)">
                  复制 JSON
                </a-button>
                <a-button
                  v-if="!record.is_builtin"
                  size="small"
                  class="api-secondary-btn"
                  :icon="h(EditOutlined)"
                  @click="openEditSceneMeta(record)"
                >
                  编辑
                </a-button>
                <a-button v-if="!record.is_builtin" size="small" class="api-secondary-btn" @click="handleToggleSceneStatus(record)">
                  {{ record.status === "enabled" ? "停用" : "启用" }}
                </a-button>
                <a-button
                  v-if="!record.is_builtin"
                  size="small"
                  class="api-danger-btn"
                  :icon="h(DeleteOutlined)"
                  @click="handleDeleteScene(record)"
                >
                  删除
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>

      <a-card title="占位符用法" class="warm-card api-card motion-fade-up motion-card-lift" style="--motion-delay: 280ms">
        <a-collapse class="warm-collapse">
          <a-collapse-panel key="common" header="通用占位符">
            <div class="doc-block">
              <div>可用于 Header JSON 或 请求 JSON：</div>
              <pre v-pre>{{ api_key }}</pre>
              <pre v-pre>{{ bearer_token }}</pre>
              <pre v-pre>{{ prompt }}</pre>
              <pre v-pre>{{ aspect_ratio }}</pre>
              <pre v-pre>{{ image_size }}</pre>
              <pre v-pre>{{ custom_size }}</pre>
              <pre v-pre>{{ mapped_resolution }}</pre>
              <pre v-pre>{{ mode }}</pre>
            </div>
          </a-collapse-panel>
          <a-collapse-panel key="image" header="图片生成相关">
            <div class="doc-block">
              <div>用于文生图或图编辑接口：</div>
              <pre v-pre>{{ contents_parts }}</pre>
              <pre v-pre>{{ generation_config }}</pre>
              <pre v-pre>{{ reference_image_1 }}</pre>
              <pre v-pre>{{ reference_image_1_base64 }}</pre>
              <pre v-pre>{{ reference_image_1_mime_type }}</pre>
              <pre v-pre>{{ reference_image_1_data_url }}</pre>
              <pre v-pre>{{ reference_image_2 }}</pre>
              <pre v-pre>{{ reference_image_3 }}</pre>
              <pre v-pre>{{ reference_image_count }}</pre>
              <div class="scene-desc">
                图编辑场景会按“最大参考图张数”限制上传与请求回填数量。支持多少张，就会尝试回填多少个
                <code v-pre>{{ reference_image_N }}</code>
                占位符；超出的图片不会进入请求。旧模板仍可继续使用
                <code v-pre>{{ contents_parts }}</code>
                兼容现有 Gemini 风格请求体。
              </div>
              <div class="scene-desc" style="margin-top: 8px">
                当某个精确占位符不存在时，例如
                <code v-pre>{{ reference_image_6_base64 }}</code>
                ，系统会自动移除当前对象或数组项，适合按上传张数动态裁剪
                <code>image</code>
                列表。
              </div>
              <div class="scene-desc" style="margin-top: 8px">例如：</div>
              <pre v-pre>{
  "input": {
    "image": "{{ reference_image_1 }}",
    "style": "{{ reference_image_2 }}",
    "referenceCount": "{{ reference_image_count }}"
  }
}</pre>
              <pre v-pre>{
  "image": [
    {
      "b64_json": "{{ reference_image_1_base64 }}"
    }
  ]
}</pre>
              <div class="scene-desc">
                宽高比、生图质量、自定义分辨率选项请在场景表单中用 JSON 数组维护，系统会把对应 value 传入
                <code v-pre>{{ aspect_ratio }}</code>
                /
                <code v-pre>{{ image_size }}</code>
                /
                <code v-pre>{{ custom_size }}</code>
                。
              </div>
              <div class="scene-desc" style="margin-top: 8px">
                如果第三方只接受一个分辨率参数，可在场景表单维护“分辨率映射 JSON”，系统会按
                <code v-pre>{{ aspect_ratio }}</code>
                +
                <code v-pre>{{ image_size }}</code>
                输出
                <code v-pre>{{ mapped_resolution }}</code>
                。
              </div>
            </div>
          </a-collapse-panel>
          <a-collapse-panel key="reverse" header="提示词反推相关">
            <div class="doc-block">
              <div>用于反推接口：</div>
              <pre v-pre>{{ image_data_url }}</pre>
              <pre v-pre>{{ prompt_reverse_text }}</pre>
            </div>
          </a-collapse-panel>
          <a-collapse-panel key="optimize" header="提示词优化相关">
            <div class="doc-block">
              <div>用于提示词优化接口：</div>
              <pre v-pre>{{ prompt }}</pre>
              <pre v-pre>{{ prompt_optimize_text }}</pre>
              <pre v-pre>{{ prompt_optimize_style_prompt }}</pre>
              <pre v-pre>{{ reference_images }}</pre>
              <pre v-pre>{{ reference_image_1_url }}</pre>
              <pre v-pre>{{ reference_image_1_data_url }}</pre>
              <pre v-pre>{{ reference_image_1_base64 }}</pre>
            </div>
          </a-collapse-panel>
        </a-collapse>
      </a-card>
    </a-space>

    <a-modal
      v-model:open="sceneModalOpen"
      :title="sceneModalTitle"
      :mask-closable="false"
      :width="720"
      @ok="handleCreateScene"
    >
      <a-form layout="vertical">
        <a-form-item label="粘贴场景绑定 JSON 回填">
          <a-textarea
            v-model:value="sceneImportJson"
            :rows="6"
            allow-clear
            class="warm-input"
            placeholder="粘贴从“复制 JSON”得到的场景绑定模板，可自动识别并回填下面的字段"
          />
          <div style="display: flex; justify-content: flex-end; margin-top: 8px">
            <a-button class="api-secondary-btn" @click="handleApplySceneImportJson">识别并回填</a-button>
          </div>
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="场景标识" required>
              <a-input v-model:value="sceneForm.scene_key" class="warm-input" placeholder="例如：banana_ultra" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="排序值">
              <a-input-number v-model:value="sceneForm.sort_order" class="warm-input-number" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="场景名称" required>
              <a-input v-model:value="sceneForm.scene_label" class="warm-input" placeholder="例如：800AI Ultra" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="消耗积分">
              <a-input-number v-model:value="sceneForm.credit_cost" class="warm-input-number" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="最大参考图张数">
          <a-input-number v-model:value="sceneForm.max_reference_images" class="warm-input-number" :min="0" style="width: 100%" />
          <div class="scene-desc" style="margin-top: 6px">
            仅图编辑场景生效；前端最多允许上传这么多张参考图，并回填对应数量的
            <code v-pre>{{ reference_image_1 }}</code>
            到
            <code v-pre>{{ reference_image_N }}</code>
            占位符。文生图场景可填 `0`。
          </div>
        </a-form-item>

        <a-form-item label="场景类型" required>
          <a-radio-group v-model:value="sceneForm.scene_type" class="warm-radio-group" button-style="solid">
            <a-radio-button value="generate">文生图</a-radio-button>
            <a-radio-button value="image_edit">图编辑</a-radio-button>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="场景描述">
          <a-input v-model:value="sceneForm.scene_description" class="warm-input" placeholder="例如：高质量增强版" />
        </a-form-item>

        <a-form-item label="默认绑定接口">
          <a-select
            v-model:value="sceneForm.api_config_id"
            class="warm-select"
            allow-clear
            placeholder="可选，创建后也可在列表中再绑定"
          >
            <a-select-option
              v-for="option in getBindingOptions()"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="备用接口">
          <a-select
            v-model:value="sceneForm.backup_api_config_id"
            class="warm-select"
            allow-clear
            placeholder="可选，主接口生成失败时自动切换"
          >
            <a-select-option
              v-for="option in getBindingOptions()"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="显示名称">
              <a-input v-model:value="sceneForm.display_name" class="warm-input" placeholder="为空则使用场景名称" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="副标题">
              <a-input v-model:value="sceneForm.subtitle" class="warm-input" placeholder="为空则使用场景描述" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="隐藏宽高比">
              <a-switch v-model:checked="sceneForm.hide_aspect_ratio" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="隐藏分辨率">
              <a-switch v-model:checked="sceneForm.hide_resolution" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="隐藏自定义分辨率">
              <a-switch v-model:checked="sceneForm.hide_custom_size" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="宽高比选项 JSON">
          <a-textarea
            v-model:value="sceneForm.aspect_ratio_options_json"
            class="warm-textarea"
            :rows="8"
            placeholder='[{"label":"1:1","value":"1:1"}]'
          />
          <div class="scene-desc" style="margin-top: 6px">
            使用 `label/value` 数组；`value` 会映射到请求里的 <code v-pre>{{ aspect_ratio }}</code> 占位符。
          </div>
        </a-form-item>

        <a-form-item label="生图质量选项 JSON">
          <a-textarea
            v-model:value="sceneForm.image_size_options_json"
            class="warm-textarea"
            :rows="6"
            placeholder='[{"label":"2K","value":"2K"}]'
          />
          <div class="scene-desc" style="margin-top: 6px">
            使用 `label/value` 数组；`value` 会映射到请求里的 <code v-pre>{{ image_size }}</code> 占位符。
          </div>
        </a-form-item>

        <a-form-item label="自定义分辨率选项 JSON">
          <a-textarea
            v-model:value="sceneForm.custom_size_options_json"
            class="warm-textarea"
            :rows="6"
            placeholder='[{"label":"1024 x 1024","value":"1024x1024"}]'
          />
          <div class="scene-desc" style="margin-top: 6px">
            使用 `label/value` 数组；`value` 会映射到请求里的 <code v-pre>{{ custom_size }}</code> 占位符。
          </div>
        </a-form-item>

        <a-form-item label="分辨率映射 JSON">
          <a-textarea
            v-model:value="sceneForm.resolution_mapping_json"
            class="warm-textarea"
            :rows="8"
            placeholder='{"1:1":{"2K":"2048x2048"},"3:4":{"2K":"1536x2048"}}'
          />
          <div class="scene-desc" style="margin-top: 6px">
            使用 `宽高比 -> 生图质量 -> 第三方分辨率` 对象；匹配结果会映射到请求里的
            <code v-pre>{{ mapped_resolution }}</code>
            占位符。
          </div>
        </a-form-item>

        <a-form-item label="分辨率积分 JSON">
          <a-textarea
            v-model:value="sceneForm.resolution_credit_costs_json"
            class="warm-textarea"
            :rows="5"
            placeholder='{"1K":2,"2K":4,"4K":8}'
          />
          <div class="scene-desc" style="margin-top: 6px">
            使用 `生图质量 -> 单张积分` 对象；未配置的分辨率会使用上方“消耗积分”作为默认值。
          </div>
        </a-form-item>
      </a-form>

      <template #footer>
        <a-space>
          <a-button class="api-secondary-btn" @click="sceneModalOpen = false">取消</a-button>
          <a-button type="primary" class="api-primary-btn" :loading="bindingCreating" @click="handleCreateScene">创建</a-button>
        </a-space>
      </template>
    </a-modal>

    <a-modal
      v-model:open="sceneMetaModalOpen"
      title="编辑场景基础信息"
      :mask-closable="false"
      :width="720"
      @ok="handleSaveSceneMeta"
    >
      <a-form layout="vertical">
        <a-form-item v-if="!editingId" label="粘贴接口配置 JSON 回填">
          <a-textarea
            v-model:value="configImportJson"
            :rows="6"
            allow-clear
            class="warm-input"
            placeholder="粘贴从“复制 JSON”得到的接口配置模板，可自动识别并回填下面的字段"
          />
          <div style="display: flex; justify-content: flex-end; margin-top: 8px">
            <a-button class="api-secondary-btn" @click="handleApplyConfigImportJson">识别并回填</a-button>
          </div>
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="场景标识" required>
              <a-input v-model:value="sceneMetaForm.scene_key" class="warm-input" placeholder="例如：banana_ultra" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="场景名称" required>
              <a-input v-model:value="sceneMetaForm.scene_label" class="warm-input" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="排序值">
              <a-input-number v-model:value="sceneMetaForm.sort_order" class="warm-input-number" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="最大参考图张数">
              <a-input-number v-model:value="sceneMetaForm.max_reference_images" class="warm-input-number" :min="0" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="场景描述">
          <a-input v-model:value="sceneMetaForm.scene_description" class="warm-input" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="隐藏宽高比">
              <a-switch v-model:checked="sceneMetaForm.hide_aspect_ratio" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="隐藏分辨率">
              <a-switch v-model:checked="sceneMetaForm.hide_resolution" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="隐藏自定义分辨率">
              <a-switch v-model:checked="sceneMetaForm.hide_custom_size" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="宽高比选项 JSON">
          <a-textarea
            v-model:value="sceneMetaForm.aspect_ratio_options_json"
            class="warm-textarea"
            :rows="8"
            placeholder='[{"label":"1:1","value":"1:1"}]'
          />
          <div class="scene-desc" style="margin-top: 6px">
            使用 `label/value` 数组；`value` 会映射到请求里的 <code v-pre>{{ aspect_ratio }}</code> 占位符。
          </div>
        </a-form-item>

        <a-form-item label="生图质量选项 JSON">
          <a-textarea
            v-model:value="sceneMetaForm.image_size_options_json"
            class="warm-textarea"
            :rows="6"
            placeholder='[{"label":"2K","value":"2K"}]'
          />
          <div class="scene-desc" style="margin-top: 6px">
            使用 `label/value` 数组；`value` 会映射到请求里的 <code v-pre>{{ image_size }}</code> 占位符。
          </div>
        </a-form-item>

        <a-form-item label="自定义分辨率选项 JSON">
          <a-textarea
            v-model:value="sceneMetaForm.custom_size_options_json"
            class="warm-textarea"
            :rows="6"
            placeholder='[{"label":"1024 x 1024","value":"1024x1024"}]'
          />
          <div class="scene-desc" style="margin-top: 6px">
            使用 `label/value` 数组；`value` 会映射到请求里的 <code v-pre>{{ custom_size }}</code> 占位符。
          </div>
        </a-form-item>

        <a-form-item label="分辨率映射 JSON">
          <a-textarea
            v-model:value="sceneMetaForm.resolution_mapping_json"
            class="warm-textarea"
            :rows="8"
            placeholder='{"1:1":{"2K":"2048x2048"},"3:4":{"2K":"1536x2048"}}'
          />
          <div class="scene-desc" style="margin-top: 6px">
            使用 `宽高比 -> 生图质量 -> 第三方分辨率` 对象；匹配结果会映射到请求里的
            <code v-pre>{{ mapped_resolution }}</code>
            占位符。
          </div>
        </a-form-item>

        <a-form-item label="分辨率积分 JSON">
          <a-textarea
            v-model:value="sceneMetaForm.resolution_credit_costs_json"
            class="warm-textarea"
            :rows="5"
            placeholder='{"1K":2,"2K":4,"4K":8}'
          />
          <div class="scene-desc" style="margin-top: 6px">
            使用 `生图质量 -> 单张积分` 对象；未配置的分辨率会使用场景默认积分。
          </div>
        </a-form-item>
      </a-form>

      <template #footer>
        <a-space>
          <a-button class="api-secondary-btn" @click="sceneMetaModalOpen = false">取消</a-button>
          <a-button type="primary" class="api-primary-btn" :loading="sceneMetaSaving" @click="handleSaveSceneMeta">保存</a-button>
        </a-space>
      </template>
    </a-modal>

    <a-modal
      v-model:open="modalOpen"
      :title="modalTitle"
      :mask-closable="false"
      :width="920"
      @ok="handleSave"
    >
      <a-form layout="vertical">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="配置名称" required>
              <a-input v-model:value="form.name" class="warm-input" placeholder="例如：800AI 主接口" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="接口分组">
              <a-input v-model:value="form.group_name" class="warm-input" placeholder="例如：800AI 系列 / 反推接口" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="描述">
          <a-input v-model:value="form.description" class="warm-input" placeholder="可选，用于备注该接口用途" />
        </a-form-item>

        <a-form-item label="请求地址" required>
          <a-input v-model:value="form.request_url" class="warm-input" placeholder="https://example.com/api" />
        </a-form-item>

        <a-form-item label="请求格式" required>
          <a-radio-group v-model:value="form.request_format" class="warm-radio-group" button-style="solid">
            <a-radio-button value="json">JSON</a-radio-button>
            <a-radio-button value="multipart">Multipart Form</a-radio-button>
          </a-radio-group>
          <div class="scene-desc" style="margin-top: 6px">
            选择 multipart 时会按表单方式发送，并自动忽略 Header JSON 中手写的 Content-Type。
          </div>
        </a-form-item>

        <a-form-item label="Header JSON" required>
          <a-textarea v-model:value="form.headers_json" class="warm-textarea" :rows="7" />
        </a-form-item>

        <a-form-item label="请求 JSON" required>
          <a-textarea v-model:value="form.payload_json" class="warm-textarea" :rows="12" />
        </a-form-item>

        <a-form-item label="响应 JSON" required>
          <a-textarea v-model:value="form.response_json" class="warm-textarea" :rows="10" />
        </a-form-item>

        <a-form-item label="结果 Base64 字段路径">
          <a-input
            v-model:value="form.result_base64_field"
            class="warm-input"
            placeholder="例如：candidates.0.content.parts.0.inlineData.data"
          />
          <div class="scene-desc" style="margin-top: 6px">
            生图完成后会按此路径读取响应中的 base64，并保存为结果图；支持点号路径与数字索引。
          </div>
        </a-form-item>

        <a-form-item label="状态">
          <a-radio-group v-model:value="form.status" class="warm-radio-group" button-style="solid">
            <a-radio-button value="enabled">启用</a-radio-button>
            <a-radio-button value="disabled">停用</a-radio-button>
          </a-radio-group>
        </a-form-item>
      </a-form>

      <template #footer>
        <a-space>
          <a-button class="api-secondary-btn" @click="modalOpen = false">取消</a-button>
          <a-button class="api-secondary-btn" :loading="testing" @click="handleTestConnection">测试连接</a-button>
          <a-button type="primary" class="api-primary-btn" :loading="saving" @click="handleSave">保存</a-button>
        </a-space>
      </template>
    </a-modal>
  </div>
</template>

<style scoped>
.page {
  padding: 4px;
}

.api-card :deep(.ant-card-head) {
  border-bottom: 1px solid #f0dfbe;
  background: linear-gradient(180deg, rgba(255, 250, 240, 0.88), rgba(255, 255, 255, 0.22));
}

.api-card :deep(.ant-card-head-title) {
  color: #5d4526;
  font-weight: 700;
}

.api-card :deep(.ant-card-body) {
  padding: 20px;
}

.secret-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.secret-label {
  margin-bottom: 8px;
  font-weight: 600;
}

.secret-input-row {
  display: flex;
  gap: 8px;
}

.api-primary-btn {
  border-color: var(--theme-accent) !important;
  background: var(--theme-accent) !important;
  color: var(--theme-accent-contrast) !important;
  border-radius: 12px !important;
  font-weight: 600;
}

.api-primary-btn:hover,
.api-primary-btn:focus {
  border-color: var(--theme-accent-strong) !important;
  background: var(--theme-accent-strong) !important;
  color: var(--theme-accent-contrast) !important;
}

.api-secondary-btn {
  border-color: var(--theme-panel-border-strong) !important;
  background: var(--theme-panel-bg-strong) !important;
  color: var(--theme-accent-text) !important;
  border-radius: 12px !important;
  font-weight: 600;
}

.api-secondary-btn:hover,
.api-secondary-btn:focus {
  border-color: var(--theme-border-strong) !important;
  background: var(--theme-control-hover-bg) !important;
  color: var(--theme-accent-text-hover) !important;
}

.api-danger-btn {
  border-color: #efb5ae !important;
  background: #fff1ef !important;
  color: #d6574b !important;
  border-radius: 12px !important;
  font-weight: 600;
}

.api-danger-btn:hover,
.api-danger-btn:focus {
  border-color: #e28980 !important;
  background: #ffe5e1 !important;
  color: #c9483d !important;
}

.api-icon-btn {
  padding-inline: 10px;
}

.secret-masked {
  min-height: 32px;
  flex: 1;
  display: flex;
  align-items: center;
  padding: 4px 11px;
  border: 1px solid var(--theme-control-border);
  border-radius: 6px;
  background: var(--theme-control-bg);
  cursor: pointer;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.api-tag {
  border-radius: 999px;
  border-width: 1px;
  font-weight: 600;
}

.api-tag-group {
  color: var(--theme-accent-text);
  background: var(--theme-panel-bg-strong);
  border-color: var(--theme-panel-border-strong);
}

.api-tag-enabled {
  color: var(--theme-accent-text);
  background: var(--theme-panel-bg-soft);
  border-color: var(--theme-panel-border-strong);
}

.api-tag-muted {
  color: var(--text-secondary);
  background: var(--theme-panel-bg-soft);
  border-color: var(--theme-panel-border);
}

.scene-title {
  font-weight: 600;
}

.scene-desc {
  color: var(--text-secondary);
  font-size: 12px;
}

.binding-copy-cell {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc-block pre {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--theme-panel-bg-soft);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.credit-unit {
  margin-left: 8px;
  color: var(--text-secondary);
}
</style>
