<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { message } from "ant-design-vue";
import { DeleteOutlined, UploadOutlined } from "@ant-design/icons-vue";
import { getGenerationModels } from "@/api/config";
import {
  createTemplate,
  createTemplateFromTask,
  getTemplateDetail,
  listTemplateTags,
  updateTemplate,
  type TemplatePayload,
  type TemplateFromTaskPayload,
} from "@/api/templates";
import { uploadReferenceImage } from "@/api/upload";
import ModelCategorySelect from "@/components/generate/ModelCategorySelect.vue";
import type { CreativeTemplate, GenerationModelOption, TemplateTag } from "@/types";

type DialogMode = "create" | "edit" | "fromTask";

interface TemplateFromTaskDraft {
  task_id: string;
  image_id: number;
  prompt: string;
  model?: string;
  reference_images: string[];
  result_image: string;
  size: string;
  resolution: string;
  custom_size?: string;
}

const emit = defineEmits<{
  saved: [];
}>();

const open = ref(false);
const saving = ref(false);
const mode = ref<DialogMode>("create");
const editingId = ref<number | null>(null);
const fromTaskDraft = ref<TemplateFromTaskDraft | null>(null);
const tags = ref<TemplateTag[]>([]);
const modelOptions = ref<GenerationModelOption[]>([]);
const refInput = ref<HTMLInputElement | null>(null);
const resultInput = ref<HTMLInputElement | null>(null);
const refUploading = ref(false);
const resultUploading = ref(false);

const form = reactive<TemplatePayload>({
  prompt: "",
  model: "banana_pro",
  reference_images: [],
  num_images: 1,
  size: "9:16",
  resolution: "2K",
  custom_size: "",
  result_image: "",
  sort_order: 0,
  tag_ids: [],
});

const sizeOptions = [
  { label: "1:1", value: "1:1" },
  { label: "2:3", value: "2:3" },
  { label: "3:2", value: "3:2" },
  { label: "3:4", value: "3:4" },
  { label: "4:3", value: "4:3" },
  { label: "9:16", value: "9:16" },
  { label: "16:9", value: "16:9" },
];

const resolutionOptions = [
  { label: "1K", value: "1K" },
  { label: "2K", value: "2K" },
  { label: "4K", value: "4K" },
];

const selectedModelOption = computed(() => modelOptions.value.find((item) => item.model_key === form.model) || null);
const generationModelSelectOptions = computed(() => (
  modelOptions.value.map((model) => ({
    value: model.model_key,
    label: model.model_label,
    description: model.model_description,
    sortOrder: model.sort_order,
    categoryId: model.category_id,
    categoryName: model.category_name,
    categoryDescription: model.category_description,
    categorySortOrder: model.category_sort_order,
  }))
));
const hideResolution = computed(() => !!selectedModelOption.value?.hide_resolution);
const hideCustomSize = computed(() => !!selectedModelOption.value?.hide_custom_size);
const customSizeOptions = computed(() => (
  selectedModelOption.value?.custom_size_options?.length
    ? selectedModelOption.value.custom_size_options
    : []
));
const imageInputsReadonly = computed(() => mode.value === "fromTask");
const title = computed(() => {
  if (mode.value === "edit") return "编辑模版";
  if (mode.value === "fromTask") return "从任务创建模版";
  return "新增模版";
});
const tagOptions = computed(() => (
  tags.value
    .filter((tag) => tag.parent_id != null)
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.name.localeCompare(b.name, "zh-CN"))
    .map((tag) => {
      const parent = tags.value.find((item) => item.id === tag.parent_id);
      return {
        label: parent ? `${parent.name} / ${tag.name}` : tag.name,
        value: tag.id,
      };
    })
));

function resetForm() {
  editingId.value = null;
  fromTaskDraft.value = null;
  form.prompt = "";
  form.model = modelOptions.value[0]?.model_key || "banana_pro";
  form.reference_images = [];
  form.num_images = 1;
  form.size = "9:16";
  form.resolution = "2K";
  form.custom_size = "";
  form.result_image = "";
  form.sort_order = 0;
  form.tag_ids = [];
}

async function loadTags() {
  try {
    tags.value = await listTemplateTags();
  } catch {
    // ignore
  }
}

async function loadModels() {
  try {
    modelOptions.value = await getGenerationModels();
    if (!modelOptions.value.some((item) => item.model_key === form.model) && modelOptions.value.length) {
      form.model = modelOptions.value[0].model_key;
    }
  } catch {
    // ignore
  }
}

async function ensureOptionsLoaded() {
  await Promise.all([
    tags.value.length ? Promise.resolve() : loadTags(),
    modelOptions.value.length ? Promise.resolve() : loadModels(),
  ]);
}

function fillForm(detail: Partial<CreativeTemplate | TemplateFromTaskDraft>) {
  form.prompt = detail.prompt || "";
  form.model = detail.model || modelOptions.value[0]?.model_key || "banana_pro";
  form.reference_images = [...(detail.reference_images || [])];
  form.num_images = 1;
  form.size = detail.size || "9:16";
  form.resolution = detail.resolution || "2K";
  form.custom_size = detail.custom_size || "";
  form.result_image = detail.result_image || "";
  form.sort_order = "sort_order" in detail ? (detail.sort_order ?? 0) : 0;
  form.tag_ids = "tags" in detail && Array.isArray(detail.tags) ? detail.tags.map((tag) => tag.id) : [];
}

async function openCreate() {
  await ensureOptionsLoaded();
  mode.value = "create";
  resetForm();
  open.value = true;
}

async function openEdit(item: CreativeTemplate) {
  await ensureOptionsLoaded();
  try {
    const detail = await getTemplateDetail(item.id);
    mode.value = "edit";
    editingId.value = item.id;
    fromTaskDraft.value = null;
    fillForm(detail);
    open.value = true;
  } catch {
    message.error("获取模版详情失败");
  }
}

async function openFromTask(draft: TemplateFromTaskDraft) {
  await ensureOptionsLoaded();
  mode.value = "fromTask";
  editingId.value = null;
  fromTaskDraft.value = draft;
  fillForm(draft);
  open.value = true;
}

function buildBasePayload(): TemplatePayload {
  return {
    prompt: form.prompt.trim(),
    model: form.model,
    reference_images: [...form.reference_images],
    num_images: 1,
    size: form.size,
    resolution: hideResolution.value ? "" : form.resolution,
    custom_size: hideCustomSize.value ? "" : form.custom_size,
    result_image: form.result_image,
    sort_order: Number.isFinite(form.sort_order) ? form.sort_order : 0,
    tag_ids: [...form.tag_ids],
  };
}

async function handleSave() {
  if (!form.prompt.trim()) {
    message.warning("请输入提示词");
    return;
  }
  if (!form.result_image) {
    message.warning("请上传结果图");
    return;
  }
  saving.value = true;
  try {
    const payload = buildBasePayload();
    if (mode.value === "fromTask") {
      if (!fromTaskDraft.value) return;
      const fromTaskPayload: TemplateFromTaskPayload = {
        task_id: fromTaskDraft.value.task_id,
        image_id: fromTaskDraft.value.image_id,
        prompt: payload.prompt,
        model: payload.model,
        size: payload.size,
        resolution: payload.resolution,
        custom_size: payload.custom_size,
        sort_order: payload.sort_order,
        tag_ids: payload.tag_ids,
      };
      await createTemplateFromTask(fromTaskPayload);
      message.success("模版创建成功");
    } else if (editingId.value) {
      await updateTemplate(editingId.value, payload);
      message.success("模版更新成功");
    } else {
      await createTemplate(payload);
      message.success("模版创建成功");
    }
    open.value = false;
    resetForm();
    emit("saved");
  } catch (err: any) {
    message.error(err.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

function handleCancel() {
  open.value = false;
  resetForm();
}

function triggerRefUpload() {
  if (imageInputsReadonly.value) return;
  refInput.value?.click();
}

function triggerResultUpload() {
  if (imageInputsReadonly.value) return;
  resultInput.value?.click();
}

async function handleRefUpload(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  if (!files.length) return;
  refUploading.value = true;
  try {
    for (const file of files) {
      const res = await uploadReferenceImage(file, "template");
      form.reference_images.push(res.url);
    }
    message.success("参考图上传成功");
  } catch {
    message.error("参考图上传失败");
  } finally {
    refUploading.value = false;
    input.value = "";
  }
}

async function handleResultUpload(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  resultUploading.value = true;
  try {
    const res = await uploadReferenceImage(file, "template");
    form.result_image = res.url;
    message.success("结果图上传成功");
  } catch {
    message.error("结果图上传失败");
  } finally {
    resultUploading.value = false;
    input.value = "";
  }
}

function removeRef(index: number) {
  if (imageInputsReadonly.value) return;
  form.reference_images.splice(index, 1);
}

onMounted(() => {
  void loadTags();
  void loadModels();
});

defineExpose({
  openCreate,
  openEdit,
  openFromTask,
});
</script>

<template>
  <a-modal
    v-model:open="open"
    :title="title"
    :confirm-loading="saving"
    :ok-button-props="{ class: 'warm-primary-btn' }"
    :cancel-button-props="{ class: 'warm-secondary-btn' }"
    ok-text="保存"
    cancel-text="取消"
    centered
    :width="760"
    @ok="handleSave"
    @cancel="handleCancel"
  >
    <a-form layout="vertical" style="margin-top: 16px">
      <a-form-item label="提示词">
        <a-textarea v-model:value="form.prompt" class="warm-textarea" :rows="5" :maxlength="2000" show-count />
      </a-form-item>

      <div class="form-grid">
        <a-form-item label="模型">
          <ModelCategorySelect
            v-model="form.model"
            class="warm-select"
            :options="generationModelSelectOptions"
            placeholder="请选择模型"
          />
        </a-form-item>
        <a-form-item label="宽高比">
          <a-select v-model:value="form.size" class="warm-select" :options="sizeOptions" />
        </a-form-item>
        <a-form-item label="排序值">
          <a-input-number v-model:value="form.sort_order" class="warm-input-number" :min="0" :precision="0" />
        </a-form-item>
        <a-form-item v-if="!hideResolution" label="分辨率">
          <a-select v-model:value="form.resolution" class="warm-select" :options="resolutionOptions" />
        </a-form-item>
        <a-form-item v-if="!hideCustomSize" label="自定义分辨率">
          <a-select
            v-model:value="form.custom_size"
            class="warm-select"
            :options="customSizeOptions"
            allow-clear
            placeholder="可选，带入 {{ custom_size }}"
          />
        </a-form-item>
        <a-form-item label="所属标签">
          <a-select
            v-model:value="form.tag_ids"
            class="warm-select"
            mode="multiple"
            :options="tagOptions"
            placeholder="选择小标签"
          />
        </a-form-item>
      </div>

      <a-form-item label="结果图">
        <div class="result-upload">
          <div class="result-preview">
            <img v-if="form.result_image" :src="form.result_image" alt="结果图" />
            <div v-else class="result-placeholder">请上传结果图</div>
          </div>
          <input ref="resultInput" type="file" accept="image/*" hidden @change="handleResultUpload" />
          <a-button
            v-if="!imageInputsReadonly"
            class="template-secondary-btn"
            :loading="resultUploading"
            @click="triggerResultUpload"
          >
            <template #icon><UploadOutlined /></template>
            上传结果图
          </a-button>
          <span v-else class="template-copy-tip">保存时会重新上传到模版目录</span>
        </div>
      </a-form-item>

      <a-form-item label="参考图片（可选）" style="margin-bottom: 0">
        <input ref="refInput" type="file" accept="image/*" multiple hidden @change="handleRefUpload" />
        <div class="ref-grid">
          <div v-for="(url, idx) in form.reference_images" :key="url + idx" class="ref-item">
            <img :src="url" alt="参考图" />
            <a-button
              v-if="!imageInputsReadonly"
              type="text"
              danger
              shape="circle"
              class="ref-remove"
              @click="removeRef(idx)"
            >
              <template #icon><DeleteOutlined /></template>
            </a-button>
          </div>
          <a-button
            v-if="!imageInputsReadonly"
            class="ref-add template-secondary-btn"
            :loading="refUploading"
            @click="triggerRefUpload"
          >
            <template #icon><UploadOutlined /></template>
            上传参考图
          </a-button>
        </div>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<style scoped lang="scss">
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.template-secondary-btn {
  border-color: #efc784 !important;
  background: #fff7e8 !important;
  color: #b16d10 !important;
  border-radius: 12px !important;
  font-weight: 600;
}

.template-secondary-btn:hover,
.template-secondary-btn:focus {
  border-color: #e1a64a !important;
  background: #fff0d3 !important;
  color: #c7770d !important;
}

.result-upload {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.result-preview {
  width: 132px;
  height: 132px;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);
  flex-shrink: 0;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
}

.result-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 13px;
}

.template-copy-tip {
  align-self: center;
  color: var(--text-secondary);
  font-size: 13px;
}

.ref-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.ref-item {
  position: relative;
  width: 84px;
  height: 84px;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid var(--theme-panel-border);
  background: var(--theme-panel-bg-soft);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
}

.ref-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  background: rgba(var(--theme-surface-strong-rgb), 0.92) !important;
  border: 1px solid var(--theme-panel-border) !important;
  color: #d6574b !important;
}

.ref-add {
  height: 84px;
  min-width: 120px;
  border-radius: 14px;
}

html:is([data-theme="dark"], [data-theme="midnight"]) .ref-remove {
  background: rgba(var(--theme-surface-strong-rgb), 0.92) !important;
  border-color: var(--theme-panel-border) !important;
  color: #de8f84 !important;
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .result-upload {
    flex-direction: column;
  }
}
</style>
