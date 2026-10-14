<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { readGenerationProgress, subscribeGenerationClock } from "@/lib/generationProgress";

const props = withDefaults(defineProps<{
  progressKey: string;
  startedAt?: string | null;
  estimateSeconds?: number | null;
  size?: number;
  complete?: boolean;
}>(), {
  startedAt: "",
  estimateSeconds: 60,
  size: 60,
  complete: false,
});

const RADIUS = 42;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const tick = ref(0);
const live = ref(false);
const displayedPercent = ref(0);
const localRunKey = `local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
let stopClock = () => {};

const progressStateKey = computed(() => `${props.progressKey}:${props.startedAt || localRunKey}`);
const rawPercent = computed(() => {
  tick.value;
  if (props.complete) return 100;
  return readGenerationProgress(progressStateKey.value, props.startedAt, props.estimateSeconds);
});
const percent = computed(() => displayedPercent.value);
const dashOffset = computed(() => CIRCUMFERENCE * (1 - percent.value / 100));

watch(
  () => [props.progressKey, props.startedAt] as const,
  ([nextKey, nextStartedAt], [previousKey, previousStartedAt]) => {
    const taskChanged = nextKey !== previousKey;
    const serverStartChanged = Boolean(previousStartedAt && nextStartedAt && previousStartedAt !== nextStartedAt);
    const serverStartCleared = Boolean(previousStartedAt && !nextStartedAt);
    if (taskChanged || serverStartChanged || serverStartCleared) {
      displayedPercent.value = 0;
    }
  },
);

watch(
  rawPercent,
  (value) => {
    displayedPercent.value = Math.max(displayedPercent.value, value);
  },
  { immediate: true },
);

onMounted(() => {
  stopClock = subscribeGenerationClock(() => {
    tick.value += 1;
  });
  requestAnimationFrame(() => {
    live.value = true;
  });
});

onBeforeUnmount(() => {
  stopClock();
});
</script>

<template>
  <div
    class="generation-progress"
    :class="{ 'is-live': live }"
    :style="{ width: `${size}px`, height: `${size}px`, fontSize: `${Math.round(size * 0.28)}px` }"
    role="progressbar"
    :aria-valuenow="percent"
    aria-valuemin="0"
    :aria-valuemax="complete ? 100 : 99"
    :aria-label="`生成进度 ${percent}%`"
  >
    <svg viewBox="0 0 100 100" aria-hidden="true">
      <circle class="generation-progress-track" cx="50" cy="50" :r="RADIUS" />
      <circle
        class="generation-progress-bar"
        cx="50"
        cy="50"
        :r="RADIUS"
        :stroke-dasharray="CIRCUMFERENCE"
        :stroke-dashoffset="dashOffset"
        transform="rotate(-90 50 50)"
      />
    </svg>
    <span class="generation-progress-label">{{ percent }}%</span>
  </div>
</template>

<style scoped>
.generation-progress {
  --ring-track: color-mix(in srgb, var(--theme-title, #4c341a) 18%, transparent);
  --ring-bar: var(--theme-accent, #c4a06a);
  --ring-text: var(--theme-accent-text, var(--theme-title, #8d7758));
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.generation-progress svg {
  width: 100%;
  height: 100%;
}

.generation-progress-track,
.generation-progress-bar {
  fill: none;
  stroke-width: 8;
}

.generation-progress-track {
  stroke: var(--ring-track);
}

.generation-progress-bar {
  stroke: var(--ring-bar);
  stroke-linecap: round;
}

.generation-progress.is-live .generation-progress-bar {
  transition: stroke-dashoffset 0.9s linear;
}

.generation-progress-label {
  position: absolute;
  color: var(--ring-text);
  font-size: 1em;
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1;
}
</style>
