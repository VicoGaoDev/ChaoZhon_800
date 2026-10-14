export const DEFAULT_GENERATION_ESTIMATE_SECONDS = 60;
export const MIN_GENERATION_ESTIMATE_SECONDS = 5;
export const MAX_GENERATION_ESTIMATE_SECONDS = 1800;
export const GENERATION_PROGRESS_CAP = 99;

// 到平均时长时进度约为 90%：1 - e^(-k) = 0.9 => k = ln(10)
const EASE_K = Math.log(10);

const progressHighWater = new Map<string, number>();
const localStartTimes = new Map<string, number>();
const clockListeners = new Set<() => void>();
let clockTimer: number | null = null;

export function normalizeGenerationEstimateSeconds(value: unknown): number {
  const seconds = Math.round(Number(value));
  if (!Number.isFinite(seconds) || seconds <= 0) return DEFAULT_GENERATION_ESTIMATE_SECONDS;
  return Math.min(
    MAX_GENERATION_ESTIMATE_SECONDS,
    Math.max(MIN_GENERATION_ESTIMATE_SECONDS, seconds),
  );
}

export function parseGenerationTimestamp(value?: string | null): number | null {
  const raw = (value || "").trim();
  if (!raw) return null;
  const normalized = raw.includes("T") ? raw : raw.replace(" ", "T");
  const time = Date.parse(normalized);
  return Number.isFinite(time) ? time : null;
}

export function generationProgressPercent(elapsedSeconds: number, estimateSeconds: unknown): number {
  const estimate = normalizeGenerationEstimateSeconds(estimateSeconds);
  const elapsed = Math.max(0, elapsedSeconds);
  const raw = 1 - Math.exp(-EASE_K * (elapsed / estimate));
  return Math.min(GENERATION_PROGRESS_CAP, Math.floor(raw * 100));
}

export function readGenerationProgress(
  key: string,
  startedAt: string | null | undefined,
  estimateSeconds: unknown,
  now = Date.now(),
): number {
  const parsed = parseGenerationTimestamp(startedAt);
  let elapsedSeconds = 0;
  if (parsed != null) {
    elapsedSeconds = Math.max(0, (now - parsed) / 1000);
  } else {
    const localStart = localStartTimes.get(key) ?? now;
    if (!localStartTimes.has(key)) localStartTimes.set(key, localStart);
    elapsedSeconds = Math.max(0, (now - localStart) / 1000);
  }
  const next = generationProgressPercent(elapsedSeconds, estimateSeconds);
  const previous = progressHighWater.get(key) ?? 0;
  const value = Math.max(previous, next);
  if (value !== previous) progressHighWater.set(key, value);
  return value;
}

export function subscribeGenerationClock(listener: () => void): () => void {
  clockListeners.add(listener);
  if (clockTimer == null && typeof window !== "undefined") {
    clockTimer = window.setInterval(() => {
      clockListeners.forEach((item) => item());
    }, 1000);
  }
  return () => {
    clockListeners.delete(listener);
    if (clockListeners.size === 0 && clockTimer != null) {
      window.clearInterval(clockTimer);
      clockTimer = null;
    }
  };
}
