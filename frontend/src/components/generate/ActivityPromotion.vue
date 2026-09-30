<script setup lang="ts">
import { computed, ref } from "vue";
import { CloseOutlined, GiftOutlined } from "@ant-design/icons-vue";
import { resolveImageUrl } from "@/api/images";
import type { ActivityItem } from "@/types";

const props = withDefaults(defineProps<{
  activity: ActivityItem | null;
  open?: boolean;
}>(), {
  open: false,
});

const emit = defineEmits<{
  (event: "update:open", value: boolean): void;
  (event: "contact"): void;
}>();

const imageSrc = computed(() => resolveImageUrl(props.activity?.image_url || ""));
const description = computed(() => props.activity?.description?.trim() || "点击查看活动详情");
const sideTabRef = ref<HTMLElement | null>(null);
const RETRACT_DURATION_MS = 520;

function openActivity() {
  if (!props.activity) return;
  emit("update:open", true);
}

function closeActivity() {
  emit("update:open", false);
}

function onOverlayLeave(el: Element, done: () => void) {
  const overlay = el as HTMLElement;
  const image = overlay.querySelector(".activity-image-button") as HTMLElement | null;
  const tab = sideTabRef.value;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!image || !tab || reduceMotion) {
    done();
    return;
  }

  const imageRect = image.getBoundingClientRect();
  const tabRect = tab.getBoundingClientRect();
  const dx = tabRect.left + tabRect.width / 2 - (imageRect.left + imageRect.width / 2);
  const dy = tabRect.top + tabRect.height / 2 - (imageRect.top + imageRect.height / 2);
  const scale = Math.max(
    0.08,
    Math.min(tabRect.width / Math.max(imageRect.width, 1), tabRect.height / Math.max(imageRect.height, 1)),
  );
  const opacityDelay = Math.round(RETRACT_DURATION_MS * 0.62);

  document.body.appendChild(image);
  image.style.position = "fixed";
  image.style.left = `${imageRect.left}px`;
  image.style.top = `${imageRect.top}px`;
  image.style.width = `${imageRect.width}px`;
  image.style.height = `${imageRect.height}px`;
  image.style.maxWidth = "none";
  image.style.maxHeight = "none";
  image.style.margin = "0";
  image.style.zIndex = "1200";
  image.style.transformOrigin = "center center";
  image.style.transition = "none";
  image.style.transform = "translate(0px, 0px) scale(1)";
  image.style.opacity = "1";
  void image.offsetWidth;
  image.style.transition = `transform ${RETRACT_DURATION_MS}ms cubic-bezier(0.45, 0.05, 0.25, 1), opacity 180ms ease ${opacityDelay}ms, border-radius ${RETRACT_DURATION_MS}ms ease`;
  image.style.transform = `translate(${dx}px, ${dy}px) scale(${scale})`;
  image.style.opacity = "0";
  image.style.borderRadius = "16px";
  window.setTimeout(() => {
    image.remove();
    done();
  }, RETRACT_DURATION_MS + 30);
}

function handleImageClick() {
  emit("contact");
}
</script>

<template>
  <div v-if="activity" ref="sideTabRef" class="activity-promotion">
    <a-tooltip
      :title="description"
      placement="left"
      overlay-class-name="activity-promotion-tooltip"
    >
      <button type="button" class="activity-side-tab" :aria-label="activity.title" @click="openActivity">
        <span class="activity-side-icon">
          <GiftOutlined />
        </span>
        <span class="activity-side-label">{{ activity.title }}</span>
      </button>
    </a-tooltip>

    <Teleport to="body">
      <transition name="activity-fade" @leave="onOverlayLeave">
        <div v-if="open" class="activity-image-overlay">
          <button
            type="button"
            class="activity-close-btn"
            aria-label="关闭活动"
            @click="closeActivity"
          >
            <CloseOutlined />
          </button>
          <button
            type="button"
            class="activity-image-button"
            :aria-label="activity.title"
            @click="handleImageClick"
          >
            <img :src="imageSrc" :alt="activity.title" />
          </button>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<style scoped lang="scss">
.activity-promotion {
  position: fixed;
  top: calc(50% + 92px);
  right: 0;
  z-index: 1060;
}

.activity-side-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 44px;
  max-height: 220px;
  padding: 12px 6px 14px;
  border: 1px solid #c45c5c;
  border-right: 0;
  border-radius: 16px 0 0 16px;
  background: linear-gradient(180deg, #d98989 0%, #c46a6a 100%);
  box-shadow: -6px 8px 20px rgba(168, 84, 84, 0.22);
  color: #fff;
  cursor: pointer;
  transition:
    background 0.2s ease,
    box-shadow 0.2s ease,
    width 0.2s ease;
}

.activity-side-tab:hover,
.activity-side-tab:focus-visible {
  width: 50px;
  background: linear-gradient(180deg, #e09a9a 0%, #b85c5c 100%);
  box-shadow: -8px 10px 24px rgba(168, 84, 84, 0.28);
  outline: none;
}

.activity-side-icon {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.92);
  color: #b85c5c;
  font-size: 14px;
  flex-shrink: 0;
}

.activity-side-label {
  writing-mode: vertical-rl;
  max-height: 148px;
  overflow: hidden;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.12em;
  line-height: 1.1;
}

.activity-image-overlay {
  position: fixed;
  inset: 0;
  z-index: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.activity-close-btn {
  position: fixed;
  top: 18px;
  right: 18px;
  z-index: 910;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.62);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.22);
}

.activity-close-btn:hover,
.activity-close-btn:focus-visible {
  background: rgba(0, 0, 0, 0.78);
  outline: none;
}

.activity-image-button {
  appearance: none;
  border: 0;
  padding: 0;
  margin: 0;
  background: transparent;
  cursor: pointer;
  max-width: min(92vw, 860px);
  max-height: min(86vh, 760px);
  display: block;
  overflow: hidden;
  border-radius: 18px;
}

.activity-image-button img {
  display: block;
  max-width: 100%;
  max-height: min(86vh, 760px);
  object-fit: contain;
  border: 0;
  border-radius: 18px;
  box-shadow: none;
}

.activity-fade-enter-active,
.activity-fade-leave-active {
  transition: background-color 0.42s ease, backdrop-filter 0.42s ease, -webkit-backdrop-filter 0.42s ease;
}

.activity-fade-enter-from,
.activity-fade-leave-to {
  background-color: transparent;
  backdrop-filter: blur(0);
  -webkit-backdrop-filter: blur(0);
}

.activity-fade-leave-active {
  pointer-events: none;
}

.activity-fade-leave-active .activity-close-btn {
  opacity: 0;
  transition: opacity 0.12s linear;
}

@media (max-width: 768px) {
  .activity-promotion {
    top: auto;
    bottom: calc(56px + env(safe-area-inset-bottom, 0px));
  }

  .activity-side-tab {
    max-height: 128px;
  }

  .activity-side-label {
    max-height: 64px;
  }
}

@media (max-width: 640px) {
  .activity-image-overlay {
    padding: 12px;
  }

  .activity-close-btn {
    top: 12px;
    right: 12px;
    width: 36px;
    height: 36px;
  }
}
</style>
