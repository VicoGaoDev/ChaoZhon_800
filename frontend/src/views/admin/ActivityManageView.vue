<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import dayjs from "dayjs";
import { message, Modal } from "ant-design-vue";
import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined, UploadOutlined, GiftOutlined } from "@ant-design/icons-vue";
import {
  createAdminActivity,
  deleteAdminActivity,
  listAdminActivities,
  updateAdminActivity,
  updateAdminActivityStatus,
} from "@/api/activities";
import { resolveImageUrl } from "@/api/images";
import { uploadReferenceImage } from "@/api/upload";
import type { ActivityItem, ActivityPayload, ActivityStatus } from "@/types";

const MAX_ACTIVITY_IMAGE_BYTES = 20 * 1024 * 1024;
const MAX_ACTIVITY_IMAGE_TEXT = "20MB";

function isSupportedActivityImage(file: File) {
  if (["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.type)) return true;
  return /\.(jpe?g|png|webp|gif)$/i.test(file.name);
}

const loading = ref(false);
const saving = ref(false);
const uploading = ref(false);
const modalOpen = ref(false);
const editingId = ref<string | null>(null);
const imageInput = ref<HTMLInputElement | null>(null);
const items = ref<ActivityItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);

const formState = reactive<ActivityPayload>({
  title: "",
  image_url: "",
  description: "",
  status: "enabled",
  sort_order: 100,
});

const columns = [
  { title: "活动图片", dataIndex: "image_url", width: 120 },
  { title: "活动标题", dataIndex: "title", width: 220, ellipsis: true },
  { title: "活动描述", dataIndex: "description", width: 360, ellipsis: true },
  { title: "排序", dataIndex: "sort_order", width: 90 },
  { title: "状态", dataIndex: "status", width: 120 },
  { title: "更新时间", dataIndex: "updated_at", width: 180 },
  { title: "操作", key: "actions", width: 220, fixed: "right" as const },
];

const modalTitle = computed(() => (editingId.value ? "编辑活动" : "新增活动"));

function formatTime(value?: string | null) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "-";
}

function resetForm() {
  editingId.value = null;
  formState.title = "";
  formState.image_url = "";
  formState.description = "";
  formState.status = "enabled";
  formState.sort_order = 100;
}

async function load() {
  loading.value = true;
  try {
    const res = await listAdminActivities(page.value, pageSize.value);
    items.value = res.items;
    total.value = res.total;
  } catch (err: any) {
    message.error(err.response?.data?.detail || "获取活动列表失败");
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  resetForm();
  modalOpen.value = true;
}

function openEdit(item: ActivityItem) {
  editingId.value = item.activity_id;
  formState.title = item.title;
  formState.image_url = item.image_url;
  formState.description = item.description || "";
  formState.status = item.status;
  formState.sort_order = Number(item.sort_order || 100);
  modalOpen.value = true;
}

function buildPayload(): ActivityPayload {
  return {
    title: formState.title.trim(),
    image_url: formState.image_url.trim(),
    description: formState.description.trim(),
    status: formState.status,
    sort_order: Number(formState.sort_order || 0),
  };
}

async function handleSave() {
  const payload = buildPayload();
  if (!payload.title) {
    message.warning("请输入活动标题");
    return;
  }
  if (!payload.image_url) {
    message.warning("请上传活动图片");
    return;
  }
  saving.value = true;
  try {
    if (editingId.value) {
      await updateAdminActivity(editingId.value, payload);
      message.success("活动已更新");
    } else {
      await createAdminActivity(payload);
      message.success("活动已创建");
    }
    modalOpen.value = false;
    resetForm();
    page.value = 1;
    await load();
  } catch (err: any) {
    message.error(err.response?.data?.detail || (editingId.value ? "更新活动失败" : "创建活动失败"));
  } finally {
    saving.value = false;
  }
}

function handleDelete(item: ActivityItem) {
  Modal.confirm({
    title: `删除活动「${item.title}」？`,
    content: "删除后 AI 生图页将不再展示该活动。",
    centered: true,
    okText: "删除",
    okType: "danger",
    cancelText: "取消",
    async onOk() {
      await deleteAdminActivity(item.activity_id);
      message.success("活动已删除");
      await load();
    },
  });
}

async function handleToggleStatus(item: ActivityItem) {
  const nextStatus: ActivityStatus = item.status === "enabled" ? "disabled" : "enabled";
  try {
    await updateAdminActivityStatus(item.activity_id, nextStatus);
    message.success(nextStatus === "enabled" ? "活动已启用" : "活动已停用");
    await load();
  } catch (err: any) {
    message.error(err.response?.data?.detail || "更新活动状态失败");
  }
}

function handlePageChange(nextPage: number, nextPageSize: number) {
  page.value = nextPage;
  pageSize.value = nextPageSize;
  void load();
}

function triggerImageUpload() {
  imageInput.value?.click();
}

async function handleImageUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (!isSupportedActivityImage(file)) {
    message.warning("仅支持上传 JPG、PNG、WEBP、GIF 图片");
    input.value = "";
    return;
  }
  if (file.size > MAX_ACTIVITY_IMAGE_BYTES) {
    message.warning(`图片大小不能超过 ${MAX_ACTIVITY_IMAGE_TEXT}`);
    input.value = "";
    return;
  }
  uploading.value = true;
  try {
    const res = await uploadReferenceImage(file, "activity");
    formState.image_url = res.url;
    message.success("活动图片上传成功");
  } catch (err: any) {
    message.error(err.response?.data?.detail || "活动图片上传失败");
  } finally {
    uploading.value = false;
    input.value = "";
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div class="warm-page motion-page-enter">
    <div class="warm-page-header motion-fade-up" style="--motion-delay: 40ms">
      <div class="warm-page-heading">
        <div class="warm-page-icon">
          <GiftOutlined />
        </div>
        <div>
          <div class="warm-page-title">活动管理</div>
          <div class="warm-page-desc">维护 AI 生图页活动弹窗和常驻横幅，启用后会面向用户展示。</div>
        </div>
      </div>
      <div class="page-actions">
        <a-button class="warm-secondary-btn" @click="load">
          <template #icon><ReloadOutlined /></template>
          刷新列表
        </a-button>
        <a-button type="primary" class="warm-primary-btn" @click="openCreate">
          <template #icon><PlusOutlined /></template>
          新增活动
        </a-button>
      </div>
    </div>

    <div class="warm-card warm-table-card motion-fade-up motion-card-lift" style="--motion-delay: 120ms">
      <a-table
        :columns="columns"
        :data-source="items"
        :loading="loading"
        row-key="activity_id"
        :pagination="{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: handlePageChange,
          onShowSizeChange: handlePageChange,
        }"
        :scroll="{ x: 1320 }"
        class="admin-mobile-table"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'image_url'">
            <div class="activity-thumb">
              <img :src="resolveImageUrl(record.image_url)" :alt="record.title" />
            </div>
          </template>
          <template v-else-if="column.dataIndex === 'description'">
            <a-tooltip :title="record.description || '-'">
              <div class="desc-summary">{{ record.description || "-" }}</div>
            </a-tooltip>
          </template>
          <template v-else-if="column.dataIndex === 'status'">
            <a-tag :color="record.status === 'enabled' ? 'green' : 'default'">
              {{ record.status === "enabled" ? "启用中" : "已停用" }}
            </a-tag>
          </template>
          <template v-else-if="column.dataIndex === 'updated_at'">
            {{ formatTime(record.updated_at) }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <div class="table-actions">
              <a-button type="link" size="small" class="action-btn action-btn-primary" @click="openEdit(record)">
                <template #icon><EditOutlined /></template>
                编辑
              </a-button>
              <a-divider type="vertical" />
              <a-button type="link" size="small" class="action-btn" @click="handleToggleStatus(record)">
                {{ record.status === "enabled" ? "停用" : "启用" }}
              </a-button>
              <a-divider type="vertical" />
              <a-button type="link" danger size="small" class="action-btn action-btn-danger" @click="handleDelete(record)">
                <template #icon><DeleteOutlined /></template>
                删除
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:open="modalOpen"
      :title="modalTitle"
      :confirm-loading="saving"
      ok-text="保存"
      cancel-text="取消"
      centered
      :width="680"
      @ok="handleSave"
    >
      <a-form layout="vertical" class="activity-form">
        <a-form-item label="活动标题" required>
          <a-input v-model:value="formState.title" :maxlength="200" show-count placeholder="请输入活动标题" />
        </a-form-item>
        <a-form-item label="活动图片" required>
          <input
            ref="imageInput"
            type="file"
            accept="image/*"
            style="display: none"
            @change="handleImageUpload"
          />
          <div class="image-upload-row">
            <div v-if="formState.image_url" class="image-preview">
              <img :src="resolveImageUrl(formState.image_url)" alt="activity image" />
            </div>
            <div v-else class="image-placeholder">暂未上传活动图片</div>
            <div class="image-upload-actions">
              <a-button class="warm-secondary-btn" :loading="uploading" @click="triggerImageUpload">
                <template #icon><UploadOutlined /></template>
                {{ formState.image_url ? "重新上传" : "上传图片" }}
              </a-button>
              <div class="image-upload-tip">建议上传清晰活动海报图，支持 JPG、PNG、WEBP、GIF，最大 20MB。</div>
            </div>
          </div>
        </a-form-item>
        <a-form-item label="活动描述">
          <a-textarea
            v-model:value="formState.description"
            :rows="4"
            :maxlength="5000"
            show-count
            placeholder="请输入活动描述，用户 hover 横幅时会展示"
          />
        </a-form-item>
        <div class="form-inline-grid">
          <a-form-item label="状态">
            <a-radio-group v-model:value="formState.status">
              <a-radio value="enabled">启用</a-radio>
              <a-radio value="disabled">停用</a-radio>
            </a-radio-group>
          </a-form-item>
          <a-form-item label="排序">
            <a-input-number v-model:value="formState.sort_order" :min="0" :max="999999" style="width: 160px" />
          </a-form-item>
        </div>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped lang="scss">
.desc-summary {
  max-width: 340px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--theme-text);
}

.activity-thumb {
  width: 72px;
  height: 48px;
  border-radius: 10px;
  overflow: hidden;
  background: var(--theme-empty-bg);
  border: 1px solid var(--theme-border);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
}

.table-actions {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}

.activity-form {
  margin-top: 12px;
}

.image-upload-row {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 16px;
  align-items: center;
}

.image-preview,
.image-placeholder {
  width: 180px;
  height: 108px;
  border-radius: 14px;
  overflow: hidden;
  background: var(--theme-empty-bg);
  border: 1px solid var(--theme-border);
}

.image-preview img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.image-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  text-align: center;
  color: var(--text-secondary);
  border-style: dashed;
}

.image-upload-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.image-upload-tip {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.form-inline-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
}

@media (max-width: 640px) {
  .image-upload-row,
  .form-inline-grid {
    grid-template-columns: 1fr;
  }
}
</style>
