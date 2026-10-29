<script setup lang="ts">
import { ClearOutlined } from "@ant-design/icons-vue";
import { computed, ref, watch } from "vue";

const props = withDefaults(defineProps<{
  open: boolean;
  value?: string;
  draftKey?: string;
  maxlength?: number;
  placeholder?: string;
}>(), {
  value: "",
  draftKey: "default",
  maxlength: 5000,
  placeholder: "描述您想要生成的内容...",
});

const emit = defineEmits<{
  "update:open": [value: boolean];
  confirm: [value: string];
}>();

const drafts = ref<Record<string, string>>({});
const confirming = ref(false);

function currentKey() {
  return props.draftKey || "default";
}

const draft = computed({
  get() {
    return drafts.value[currentKey()] ?? "";
  },
  set(value: string) {
    if (confirming.value) return;
    const key = currentKey();
    drafts.value = { ...drafts.value, [key]: value };
  },
});

watch(() => props.open, (open) => {
  if (!open) return;
  const key = currentKey();
  drafts.value = { ...drafts.value, [key]: props.value || "" };
}, { immediate: true });

function closeDialog() {
  emit("update:open", false);
}

function clearDraft() {
  draft.value = "";
}

function handleConfirm() {
  const key = currentKey();
  const text = draft.value;
  confirming.value = true;
  emit("confirm", text);
  drafts.value = { ...drafts.value, [key]: text };
  emit("update:open", false);
  window.setTimeout(() => {
    confirming.value = false;
  }, 0);
}
</script>

<template>
  <a-modal
    :open="open"
    title="编辑提示词"
    centered
    :width="760"
    wrap-class-name="prompt-expand-dialog"
    :body-style="{ padding: '12px 16px 4px' }"
    @update:open="(value: boolean) => emit('update:open', value)"
    @cancel="closeDialog"
  >
    <div class="prompt-expand-input-wrap">
      <a-tooltip v-if="draft" title="清空">
        <button
          type="button"
          class="prompt-expand-clear-btn"
          aria-label="清空提示词"
          @click="clearDraft"
        >
          <ClearOutlined />
        </button>
      </a-tooltip>
      <a-textarea
        v-model:value="draft"
        class="prompt-expand-input"
        :maxlength="maxlength"
        :placeholder="placeholder"
        :auto-size="false"
        show-count
        autofocus
      />
    </div>
    <template #footer>
      <a-button @click="closeDialog">取消</a-button>
      <a-button type="primary" @click="handleConfirm">确认</a-button>
    </template>
  </a-modal>
</template>

<style scoped>
.prompt-expand-input-wrap {
  position: relative;
}

.prompt-expand-clear-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: rgba(127, 107, 80, 0.45);
  color: #fffaf3;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.18s ease, transform 0.18s ease;
}

.prompt-expand-clear-btn:hover {
  background: rgba(127, 107, 80, 0.72);
  transform: scale(1.04);
}

.prompt-expand-input {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
}

.prompt-expand-input :deep(textarea) {
  min-height: min(56vh, 520px);
  resize: none;
  line-height: 1.7;
  font-size: 15px;
  color: var(--theme-title, #3d2f22);
  border-radius: 14px !important;
  border-color: var(--theme-control-border, #ebd9c1) !important;
  background: var(--theme-control-bg, #fffaf3) !important;
  padding: 14px 48px 36px 16px !important;
}

.prompt-expand-input :deep(textarea:hover),
.prompt-expand-input :deep(textarea:focus) {
  border-color: var(--theme-border-accent, #efc784) !important;
  box-shadow: 0 0 0 3px var(--theme-focus-ring, rgba(247, 168, 49, 0.18));
}

.prompt-expand-input :deep(.ant-input-data-count),
.prompt-expand-input :deep(.ant-input-textarea-show-count)::after {
  color: var(--theme-title, #3d2f22) !important;
  font-size: 12px;
}
</style>
