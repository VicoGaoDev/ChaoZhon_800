<script setup lang="ts">
import { defineAsyncComponent, onBeforeUnmount, onMounted, ref, computed } from "vue";
import { ArrowRightOutlined, CheckCircleFilled, FireOutlined, SafetyCertificateOutlined, ThunderboltOutlined } from "@ant-design/icons-vue";
import { useRouter } from "vue-router";
import { getGenerationModels } from "@/api/config";
import { getTemplateDetail, listTemplates } from "@/api/templates";
import { resolvePreviewImageUrl } from "@/api/images";
import type { CreativeTemplate, GenerationModelOption } from "@/types";

const router = useRouter();
const TemplateDetailDialog = defineAsyncComponent(() => import("@/components/templates/TemplateDetailDialog.vue"));
const showcaseItems = ref<CreativeTemplate[]>([]);
const loadingShowcase = ref(true);
const generationModels = ref<GenerationModelOption[]>([]);
const detailOpen = ref(false);
const detailLoading = ref(false);
const detail = ref<CreativeTemplate | null>(null);
let nonCriticalLoadTimer: number | null = null;
let nonCriticalIdleCallbackId: number | null = null;

const highlights = [
  {
    title: "生图更稳定",
    desc: "高峰期也保持稳定出图节奏，减少排队与失败波动，让创作流程更连贯。",
    icon: SafetyCertificateOutlined,
  },
  {
    title: "质量更在线",
    desc: "聚焦人物质感、构图一致性与细节表现，适合高质量商业视觉产出。",
    icon: FireOutlined,
  },
  {
    title: "上手更直接",
    desc: "从创意模版到自定义绘图，少走弯路，快速拿到可用结果。",
    icon: ThunderboltOutlined,
  },
];

const promises = [
  "稳定队列与任务流转，减少重复提交",
  "高质量模型配置，成图质感更统一",
  "历史记录可回看，便于复用优质结果",
];

const marqueeItems = computed(() => [...showcaseItems.value, ...showcaseItems.value]);
const idleWindow = window as Window & typeof globalThis & {
  requestIdleCallback?: (callback: IdleRequestCallback, options?: IdleRequestOptions) => number;
  cancelIdleCallback?: (handle: number) => void;
};

async function loadShowcase() {
  loadingShowcase.value = true;
  try {
    const res = await listTemplates({ page: 1, pageSize: 12 });
    showcaseItems.value = res.items.filter((item) => !!item.result_image).slice(0, 10);
  } catch {
    showcaseItems.value = [];
  } finally {
    loadingShowcase.value = false;
  }
}

async function loadModels() {
  try {
    generationModels.value = await getGenerationModels();
  } catch {
    generationModels.value = [];
  }
}

function scheduleNonCriticalHomeLoads() {
  requestAnimationFrame(() => {
    if (typeof idleWindow.requestIdleCallback === "function") {
      nonCriticalIdleCallbackId = idleWindow.requestIdleCallback(() => {
        nonCriticalIdleCallbackId = null;
        void loadModels();
        void loadShowcase();
      }, { timeout: 1500 });
      return;
    }

    nonCriticalLoadTimer = window.setTimeout(() => {
      nonCriticalLoadTimer = null;
      void loadModels();
      void loadShowcase();
    }, 180);
  });
}

async function openDetail(id: number) {
  detailOpen.value = true;
  detailLoading.value = true;
  try {
    detail.value = await getTemplateDetail(id);
  } catch {
    detailOpen.value = false;
  } finally {
    detailLoading.value = false;
  }
}

function useTemplate() {
  if (!detail.value) return;
  localStorage.setItem(
    "generateDraftFromTemplate",
    JSON.stringify({
      model: detail.value.model,
      prompt: detail.value.prompt,
      reference_images: detail.value.reference_images,
      num_images: 1,
      size: detail.value.size,
      resolution: detail.value.resolution,
      custom_size: detail.value.custom_size,
    })
  );
  detailOpen.value = false;
  router.push("/generate");
}

onMounted(() => {
  scheduleNonCriticalHomeLoads();
});

onBeforeUnmount(() => {
  if (nonCriticalLoadTimer !== null) window.clearTimeout(nonCriticalLoadTimer);
  if (nonCriticalIdleCallbackId !== null && typeof idleWindow.cancelIdleCallback === "function") {
    idleWindow.cancelIdleCallback(nonCriticalIdleCallbackId);
  }
});
</script>

<template>
  <div class="home-page warm-page motion-page-enter">
    <section class="section-block showcase-shell motion-fade-up" style="--motion-delay: 0.04s">
      <div v-if="loadingShowcase" class="showcase-skeleton-row">
        <div v-for="index in 6" :key="index" class="showcase-skeleton-card">
          <div class="showcase-skeleton-media" />
          <div class="showcase-skeleton-line showcase-skeleton-line-long" />
          <div class="showcase-skeleton-line showcase-skeleton-line-short" />
        </div>
      </div>
      <div v-else-if="showcaseItems.length" class="showcase-marquee">
        <div class="showcase-track showcase-track-single">
          <div
            v-for="(item, index) in marqueeItems"
            :key="`${item.id}-${index}`"
            class="showcase-card"
            @click="openDetail(item.id)"
          >
            <img
              :src="resolvePreviewImageUrl(item.result_image_thumb || item.result_image)"
              :alt="item.prompt || '效果图'"
              loading="lazy"
            />
            <div class="showcase-card-mask">
              <div class="showcase-card-prompt">{{ item.prompt || "高质量稳定生图结果" }}</div>
            </div>
            <div class="showcase-overlay">
              <div class="showcase-overlay-text">查看详情</div>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="showcase-empty">
        <div class="showcase-empty-title">高质量效果图展示位</div>
        <div class="showcase-empty-desc">模版结果图加载后，这里会自动横向滚动展示真实效果。</div>
      </div>
    </section>

    <section class="hero-section">
      <div class="hero-copy motion-slide-left" style="--motion-delay: 0.08s">
        <div class="hero-badge">
          <CheckCircleFilled />
          <span>稳定出图体验</span>
        </div>
        <h1 class="hero-title">更稳定、更高质的 AI 生图工作台</h1>
        <p class="hero-desc">
          面向日常创作与商业视觉场景，强调稳定生成、细节质量与可持续复用的创作体验。
          从灵感探索到正式出图，都能保持更顺滑的节奏。
        </p>
        <div class="hero-actions">
          <a-button type="primary" size="large" class="warm-primary-btn" @click="router.push('/generate')">
            <template #icon><ArrowRightOutlined /></template>
            立即开始生图
          </a-button>
          <a-button size="large" class="hero-secondary-btn" @click="router.push('/templates')">
            浏览创意模版
          </a-button>
        </div>
        <div class="hero-metrics">
          <div class="metric-card">
            <strong>更稳定</strong>
            <span>减少失败与波动感</span>
          </div>
          <div class="metric-card">
            <strong>更高质</strong>
            <span>注重细节、构图与质感</span>
          </div>
          <div class="metric-card">
            <strong>更省心</strong>
            <span>模版、历史与复用链路完整</span>
          </div>
        </div>
      </div>

      <div class="hero-visual motion-slide-right" style="--motion-delay: 0.14s">
        <div class="hero-glow hero-glow-main" />
        <div class="hero-glow hero-glow-sub" />
        <div class="hero-panel hero-panel-primary">
          <div class="panel-label">核心价值</div>
          <div class="panel-title">稳定与质量并重</div>
          <p>为需要持续产出的生图场景提供更可靠的结果表现。</p>
        </div>
        <div class="hero-panel hero-panel-floating">
          <div class="panel-dot" />
          <span>更适合持续创作</span>
        </div>
      </div>
    </section>

    <section class="section-block motion-fade-up" style="--motion-delay: 0.18s">
      <div class="section-heading">
        <div class="section-title">为什么用 800AI</div>
        <div class="section-desc">不是只强调“能生成”，而是强调“稳定地生成出更好的图”。</div>
      </div>

      <div class="highlight-grid">
        <div v-for="item in highlights" :key="item.title" class="highlight-card warm-card motion-card-lift">
          <div class="highlight-icon">
            <component :is="item.icon" />
          </div>
          <div class="highlight-title">{{ item.title }}</div>
          <div class="highlight-desc">{{ item.desc }}</div>
        </div>
      </div>
    </section>

    <section class="section-block promise-shell motion-fade-up" style="--motion-delay: 0.24s">
      <div class="section-heading">
        <div class="section-title">适合追求成图质量的工作流</div>
        <div class="section-desc">无论是营销海报、人物视觉、商品图，还是创意概念稿，都更强调结果可用性。</div>
      </div>

      <div class="promise-list">
        <div v-for="item in promises" :key="item" class="promise-item">
          <CheckCircleFilled />
          <span>{{ item }}</span>
        </div>
      </div>

      <div class="promise-actions">
        <a-button size="large" class="hero-secondary-btn" @click="router.push('/history')">查看历史记录</a-button>
        <a-button type="primary" size="large" class="warm-primary-btn" @click="router.push('/generate')">进入自定义绘图</a-button>
      </div>
    </section>

    <TemplateDetailDialog
      v-if="detailOpen"
      v-model:open="detailOpen"
      :loading="detailLoading"
      :detail="detail"
      :generation-models="generationModels"
      @use-template="useTemplate"
    />
  </div>
</template>

<style scoped lang="scss">
.home-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-height: calc(100vh - 130px);
}

.hero-section {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
  gap: 24px;
  padding: 18px 0 8px;
  background:
    radial-gradient(circle at top right, rgba(255, 210, 109, 0.3), transparent 34%),
    linear-gradient(180deg, rgba(255, 253, 248, 0.86), rgba(255, 246, 232, 0.68));
}

.hero-copy {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255, 244, 215, 0.95);
  color: #a36912;
  font-size: 13px;
  font-weight: 700;
}

.hero-title {
  margin: 0;
  color: #4c341a;
  font-size: clamp(34px, 5vw, 54px);
  line-height: 1.08;
  letter-spacing: -0.03em;
}

.hero-desc {
  max-width: 700px;
  margin: 0;
  color: #755b39;
  font-size: 16px;
  line-height: 1.8;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.hero-secondary-btn {
  height: 44px;
  padding-inline: 20px;
  border-radius: 14px;
  border-color: #efd2a1;
  color: #9b6110;
  background: rgba(255, 250, 242, 0.92);
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 6px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(241, 221, 183, 0.9);

  strong {
    color: #5b4120;
    font-size: 16px;
  }

  span {
    color: #8a7250;
    font-size: 13px;
    line-height: 1.6;
  }
}

.hero-visual {
  position: relative;
  min-height: 360px;
  border-radius: 28px;
  background:
    radial-gradient(circle at 30% 28%, rgba(255, 214, 134, 0.52), transparent 18%),
    radial-gradient(circle at 70% 30%, rgba(255, 236, 195, 0.75), transparent 24%),
    linear-gradient(180deg, rgba(255, 248, 235, 0.96), rgba(255, 240, 208, 0.9));
  border: 1px solid rgba(241, 210, 154, 0.65);
}

.hero-glow {
  position: absolute;
  border-radius: 999px;
  filter: blur(10px);
}

.hero-glow-main {
  top: 40px;
  right: 36px;
  width: 120px;
  height: 120px;
  background: rgba(255, 197, 93, 0.36);
}

.hero-glow-sub {
  left: 30px;
  bottom: 56px;
  width: 150px;
  height: 150px;
  background: rgba(255, 232, 188, 0.55);
}

.hero-panel {
  position: absolute;
  border-radius: 24px;
  background: rgba(255, 253, 249, 0.88);
  border: 1px solid rgba(241, 221, 183, 0.88);
  box-shadow: 0 16px 30px rgba(236, 185, 88, 0.12);
}

.hero-panel-primary {
  left: 36px;
  right: 52px;
  top: 54px;
  padding: 24px;

  p {
    margin: 0;
    color: #82694a;
    line-height: 1.8;
  }
}

.panel-label {
  margin-bottom: 8px;
  color: #bf8c45;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.panel-title {
  margin-bottom: 10px;
  color: #50371b;
  font-size: 24px;
  font-weight: 800;
}

.hero-panel-floating {
  right: 38px;
  bottom: 42px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  color: #6f522a;
  font-weight: 700;
}

.panel-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(180deg, #ffd06d, #ffab25);
  box-shadow: 0 0 0 6px rgba(255, 208, 109, 0.18);
}

.section-block {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.section-heading {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  color: #4f361b;
  font-size: 26px;
  font-weight: 800;
}

.section-desc {
  color: #866b49;
  line-height: 1.8;
}

.highlight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.showcase-shell {
  padding: 8px 0 12px;
  overflow: hidden;
}

.showcase-skeleton-row {
  display: flex;
  gap: 16px;
  overflow: hidden;
}

.showcase-skeleton-card {
  width: 184px;
  flex: 0 0 auto;
  padding: 10px;
  border-radius: 18px;
  background: linear-gradient(180deg, #fffaf3, #fff4e7);
  border: 1px solid rgba(241, 210, 154, 0.5);
}

.showcase-skeleton-media,
.showcase-skeleton-line {
  position: relative;
  overflow: hidden;
  background: #f4e9d5;

  &::after {
    content: "";
    position: absolute;
    inset: 0;
    transform: translateX(-100%);
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.65), transparent);
    animation: showcase-skeleton-shimmer 1.4s ease-in-out infinite;
  }
}

.showcase-skeleton-media {
  height: 180px;
  border-radius: 14px;
  margin-bottom: 12px;
}

.showcase-skeleton-line {
  height: 10px;
  border-radius: 999px;
}

.showcase-skeleton-line-long {
  width: 88%;
  margin-bottom: 8px;
}

.showcase-skeleton-line-short {
  width: 56%;
}

.showcase-marquee {
  position: relative;
  overflow: hidden;
  padding-top: 4px;

  &::before,
  &::after {
    content: "";
    position: absolute;
    top: 0;
    bottom: 0;
    width: 72px;
    z-index: 2;
    pointer-events: none;
  }

  &::before {
    left: 0;
    background: linear-gradient(90deg, #fffaf2 0%, rgba(255, 250, 242, 0) 100%);
  }

  &::after {
    right: 0;
    background: linear-gradient(270deg, #fffaf2 0%, rgba(255, 250, 242, 0) 100%);
  }
}

.showcase-track {
  display: flex;
  gap: 16px;
  width: max-content;
}
.showcase-track-single {
  animation: showcase-scroll-left 38s linear infinite;
}

.showcase-marquee:hover .showcase-track {
  animation-play-state: paused;
}

.showcase-card {
  position: relative;
  width: 184px;
  height: 236px;
  flex: 0 0 auto;
  border-radius: 18px;
  overflow: hidden;
  background: #fff4e6;
  border: 1px solid rgba(241, 210, 154, 0.7);
  box-shadow: 0 16px 28px rgba(236, 185, 88, 0.12);
  cursor: pointer;
  transition:
    transform var(--motion-duration-hover) var(--motion-ease-enter),
    box-shadow var(--motion-duration-hover) var(--motion-ease-soft),
    border-color var(--motion-duration-hover) var(--motion-ease-soft);

  img {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
    transition: transform var(--motion-duration-emphasis) var(--motion-ease-enter);
  }

  &:hover {
    transform: translateY(-6px);
    border-color: #f0c46d;
    box-shadow: 0 22px 40px rgba(236, 185, 88, 0.2);
  }

  &:hover img {
    transform: scale(1.045);
  }
}

.showcase-card-mask {
  position: absolute;
  inset: auto 0 0 0;
  padding: 14px 12px 12px;
  background: linear-gradient(180deg, rgba(53, 37, 18, 0) 0%, rgba(53, 37, 18, 0.78) 100%);
}

.showcase-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(34, 25, 14, 0.08), rgba(34, 25, 14, 0.56));
  opacity: 0;
  transition: opacity var(--motion-duration-base) var(--motion-ease-soft);

  .showcase-card:hover & {
    opacity: 1;
  }
}

.showcase-overlay-text {
  padding: 10px 18px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  color: #5d4526;
  font-size: 14px;
  font-weight: 700;
  transition: transform var(--motion-duration-swift) var(--motion-ease-soft);

  .showcase-card:hover & {
    transform: translateY(-2px);
  }
}

.showcase-card-prompt {
  color: #fff8ef;
  font-size: 12px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.showcase-empty {
  margin: 8px 26px 0;
  padding: 34px 20px;
  border-radius: 24px;
  border: 1px dashed #efd3a1;
  background: linear-gradient(180deg, #fffaf3, #fff6ea);
  text-align: center;
}

.showcase-empty-title {
  color: #5b4120;
  font-size: 18px;
  font-weight: 800;
}

.showcase-empty-desc {
  margin-top: 8px;
  color: #8a7250;
  line-height: 1.8;
}

.highlight-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 22px;
  border-radius: 24px;
}

.highlight-icon {
  width: 50px;
  height: 50px;
  border-radius: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #fff1cf, #ffe2a8);
  color: #ad6d0a;
  font-size: 22px;
  box-shadow: 0 12px 20px rgba(236, 185, 88, 0.14);
}

.highlight-title {
  color: #553a1d;
  font-size: 18px;
  font-weight: 800;
}

.highlight-desc {
  color: #866b49;
  line-height: 1.8;
}

.promise-shell {
  padding: 6px 0 0;
}

.promise-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.promise-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 16px 18px;
  border-radius: 18px;
  background: #fffaf1;
  border: 1px solid #f1dfbf;
  color: #6f5634;
  line-height: 1.8;

  .anticon {
    margin-top: 4px;
    color: #d08a15;
  }
}

.promise-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 6px;
}

:global(html[data-theme="dark"]),
:global(html[data-theme="midnight"]) {
  .home-page {
    .hero-section,
    .hero-visual,
    .hero-panel,
    .metric-card,
    .showcase-skeleton-card,
    .showcase-card,
    .showcase-empty,
    .promise-item,
    .hero-secondary-btn {
      background: var(--theme-panel-bg) !important;
      border-color: var(--theme-panel-border) !important;
      box-shadow: none !important;
    }

    .highlight-card.warm-card {
      background: transparent !important;
      border-color: transparent !important;
      box-shadow: none !important;
    }

    .highlight-card.warm-card.motion-card-lift {
      transition: none !important;
    }

    .highlight-card.warm-card:hover {
      background: transparent !important;
      border-color: transparent !important;
      box-shadow: none !important;
      transform: none !important;
    }

    .hero-section {
      background: transparent !important;
    }

    .hero-visual {
      border: 1px solid var(--theme-panel-border);
    }

    .hero-glow-main,
    .hero-glow-sub {
      background: var(--theme-overlay-soft) !important;
    }

    .hero-badge {
      background: var(--theme-panel-bg) !important;
      border: 1px solid var(--theme-panel-border);
      color: var(--theme-title) !important;
    }

    .hero-title,
    .section-title,
    .panel-title,
    .showcase-empty-title,
    .highlight-title {
      color: var(--theme-title) !important;
    }

    .hero-desc,
    .section-desc,
    .showcase-empty-desc,
    .highlight-desc,
    .promise-item,
    .panel-label,
    .hero-panel-primary p,
    .hero-panel-floating {
      color: var(--text-secondary) !important;
    }

    .panel-dot,
    .highlight-icon {
      background: var(--theme-accent) !important;
      color: var(--theme-accent-contrast) !important;
      box-shadow: none !important;
    }

    .showcase-skeleton-card {
      border: 1px solid var(--theme-panel-border);
    }

    .showcase-skeleton-media,
    .showcase-skeleton-line {
      background: var(--theme-panel-bg-strong) !important;
    }

    .showcase-marquee::before {
      background: linear-gradient(90deg, var(--theme-panel-bg) 0%, rgba(var(--theme-surface-strong-rgb), 0) 100%) !important;
    }

    .showcase-marquee::after {
      background: linear-gradient(270deg, var(--theme-panel-bg) 0%, rgba(var(--theme-surface-strong-rgb), 0) 100%) !important;
    }

    .showcase-card {
      border: 1px solid var(--theme-panel-border);

      &:hover {
        border-color: var(--theme-border-strong) !important;
        box-shadow: 0 10px 24px var(--theme-shadow-soft) !important;
      }
    }

    .showcase-card-mask {
      background: linear-gradient(180deg, rgba(22, 24, 29, 0) 0%, var(--theme-overlay-heavy) 100%) !important;
    }

    .showcase-card-prompt {
      color: var(--theme-accent-contrast) !important;
    }

    .showcase-overlay {
      background: linear-gradient(180deg, var(--theme-overlay-soft), var(--theme-overlay-strong)) !important;
    }

    .showcase-overlay-text {
      background: rgba(var(--theme-surface-strong-rgb), 0.96) !important;
      color: var(--theme-accent-text-hover) !important;
      border: 1px solid var(--theme-panel-border);
    }

    .showcase-empty {
      border: 1px dashed var(--theme-panel-border) !important;
    }

    .metric-card strong {
      color: var(--theme-title) !important;
    }

    .metric-card span {
      color: var(--text-secondary) !important;
    }

    .promise-item {
      .anticon {
        color: var(--theme-accent) !important;
      }
    }
  }
}

@keyframes showcase-scroll-left {
  from {
    transform: translate3d(0, 0, 0);
  }
  to {
    transform: translate3d(calc(-50% - 8px), 0, 0);
  }
}

@keyframes showcase-skeleton-shimmer {
  to {
    transform: translateX(100%);
  }
}

@media (max-width: 1100px) {
  .hero-section,
  .highlight-grid,
  .promise-list {
    grid-template-columns: 1fr;
  }

  .hero-visual {
    min-height: 300px;
  }

  .hero-metrics {
    grid-template-columns: 1fr;
  }

  .showcase-card {
    width: 164px;
    height: 214px;
  }

  .showcase-skeleton-card {
    width: 164px;
  }

  .showcase-skeleton-media {
    height: 160px;
  }
}

@media (max-width: 640px) {
  .hero-section,
  .promise-shell {
    padding-inline: 0;
  }

  .hero-title {
    font-size: 32px;
  }

  .hero-panel-primary {
    left: 20px;
    right: 20px;
    top: 24px;
    padding: 20px;
  }

  .hero-panel-floating {
    right: 20px;
    bottom: 20px;
    left: 20px;
    justify-content: center;
  }

  .showcase-empty {
    margin-inline: 18px;
  }

  .showcase-card {
    width: 142px;
    height: 190px;
    border-radius: 16px;
  }

  .showcase-skeleton-card {
    width: 142px;
    border-radius: 16px;
  }

  .showcase-skeleton-media {
    height: 136px;
  }
}
</style>

<style lang="scss">
html[data-theme="dark"] .home-page .hero-section.hero-section,
html[data-theme="midnight"] .home-page .hero-section.hero-section {
  background: var(--theme-page-base) !important;
  border: none !important;
  box-shadow: none !important;
  border-radius: 0 !important;
}

html[data-theme="dark"] .home-page .section-block,
html[data-theme="dark"] .home-page .showcase-shell,
html[data-theme="dark"] .home-page .promise-shell,
html[data-theme="midnight"] .home-page .section-block,
html[data-theme="midnight"] .home-page .showcase-shell,
html[data-theme="midnight"] .home-page .promise-shell {
  background: var(--theme-page-base) !important;
  border-color: transparent !important;
  box-shadow: none !important;
  border-radius: 0 !important;
}

html[data-theme="dark"] .home-page .showcase-marquee,
html[data-theme="dark"] .home-page .showcase-skeleton-row,
html[data-theme="midnight"] .home-page .showcase-marquee,
html[data-theme="midnight"] .home-page .showcase-skeleton-row {
  background: var(--theme-page-base) !important;
}

html[data-theme="dark"] .home-page .showcase-marquee::before,
html[data-theme="midnight"] .home-page .showcase-marquee::before {
  background: linear-gradient(90deg, var(--theme-page-base) 0%, rgba(var(--theme-page-base-rgb), 0) 100%) !important;
}

html[data-theme="dark"] .home-page .showcase-marquee::after,
html[data-theme="midnight"] .home-page .showcase-marquee::after {
  background: linear-gradient(270deg, var(--theme-page-base) 0%, rgba(var(--theme-page-base-rgb), 0) 100%) !important;
}

html[data-theme="dark"] .home-page .highlight-card.warm-card,
html[data-theme="midnight"] .home-page .highlight-card.warm-card {
  background: var(--theme-panel-bg) !important;
  border: 1px solid var(--theme-panel-border) !important;
  box-shadow: 0 10px 24px var(--theme-shadow-soft) !important;
}

html[data-theme="dark"] .home-page .metric-card,
html[data-theme="dark"] .home-page .promise-item,
html[data-theme="midnight"] .home-page .metric-card,
html[data-theme="midnight"] .home-page .promise-item {
  background: var(--theme-panel-bg) !important;
  border-color: var(--theme-panel-border) !important;
  box-shadow: none !important;
}

html[data-theme="dark"] .home-page .hero-panel,
html[data-theme="dark"] .home-page .hero-secondary-btn,
html[data-theme="dark"] .home-page .hero-badge,
html[data-theme="dark"] .home-page .showcase-empty,
html[data-theme="midnight"] .home-page .hero-panel,
html[data-theme="midnight"] .home-page .hero-secondary-btn,
html[data-theme="midnight"] .home-page .hero-badge,
html[data-theme="midnight"] .home-page .showcase-empty {
  background: var(--theme-panel-bg) !important;
  box-shadow: none !important;
}
</style>
