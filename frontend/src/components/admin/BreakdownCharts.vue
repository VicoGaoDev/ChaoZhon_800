<script setup lang="ts">
import { computed } from "vue";
import type { PropType } from "vue";
import type { AdminAnalyticsBreakdown } from "@/types";
import { VChart } from "./charting";

const props = defineProps({
  data: {
    type: Object as PropType<AdminAnalyticsBreakdown | null>,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits<{
  (e: "filter-click", payload: { type: "status" | "source" | "mode" | "model" | "user"; value: string }): void;
}>();

const hasBreakdownData = computed(() => {
  if (!props.data) return false;
  return [
    ...props.data.status_breakdown,
    ...props.data.source_breakdown,
    ...props.data.mode_breakdown,
    ...props.data.model_breakdown,
    ...props.data.top_users_by_tasks,
    ...props.data.top_users_by_credit,
  ].some((item) => item.count > 0 || item.credit_cost > 0);
});

function statusLabel(value: string) {
  const map: Record<string, string> = {
    pending: "等待中",
    processing: "处理中",
    success: "成功",
    failed: "失败",
  };
  return map[value] || value;
}

function modeLabel(value: string) {
  if (value === "text_generate") return "文生图";
  if (value === "image_edit") return "图编辑";
  if (value === "inpaint") return "局部重绘";
  if (value === "promptReverse") return "提示词反推";
  if (value === "promptOptimize") return "提示词优化";
  return value;
}

function sourceLabel(value: string) {
  if (value === "app") return "App";
  if (value === "api") return "API";
  return "Web";
}

const statusPieOption = computed(() => ({
  color: ["#52c41a", "#ff4d4f", "#fa8c16", "#91caff"],
  tooltip: {
    trigger: "item",
    backgroundColor: "rgba(76, 52, 26, 0.92)",
    borderWidth: 0,
    textStyle: { color: "#fffdf8" },
  },
  legend: { bottom: 0 },
  series: [
    {
      type: "pie",
      radius: ["42%", "68%"],
      data: (props.data?.status_breakdown || []).map((item) => ({
        name: statusLabel(item.name),
        value: item.count,
        rawValue: item.name,
      })),
    },
  ],
}));

const modePieOption = computed(() => ({
  color: ["#1890ff", "#722ed1", "#13c2c2"],
  tooltip: {
    trigger: "item",
    backgroundColor: "rgba(76, 52, 26, 0.92)",
    borderWidth: 0,
    textStyle: { color: "#fffdf8" },
  },
  legend: { bottom: 0 },
  series: [
    {
      type: "pie",
      radius: ["42%", "68%"],
      data: (props.data?.mode_breakdown || []).map((item) => ({
        name: modeLabel(item.name),
        value: item.count,
        rawValue: item.name,
      })),
    },
  ],
}));

const sourcePieOption = computed(() => ({
  color: ["#1890ff", "#722ed1"],
  tooltip: {
    trigger: "item",
    backgroundColor: "rgba(76, 52, 26, 0.92)",
    borderWidth: 0,
    textStyle: { color: "#fffdf8" },
  },
  legend: { bottom: 0 },
  series: [
    {
      type: "pie",
      radius: ["42%", "68%"],
      data: (props.data?.source_breakdown || []).map((item) => ({
        name: sourceLabel(item.name),
        value: item.count,
        rawValue: item.name,
      })),
    },
  ],
}));

const modelBarOption = computed(() => ({
  tooltip: {
    trigger: "axis",
    backgroundColor: "rgba(76, 52, 26, 0.92)",
    borderWidth: 0,
    textStyle: { color: "#fffdf8" },
  },
  grid: { left: 40, right: 20, top: 20, bottom: 48 },
  xAxis: { type: "category", data: (props.data?.model_breakdown || []).map((item) => item.name), axisLabel: { interval: 0, rotate: 18 } },
  yAxis: { type: "value" },
  series: [
    {
      type: "bar",
      data: (props.data?.model_breakdown || []).map((item) => item.count),
      itemStyle: { color: "#1890ff", borderRadius: [8, 8, 0, 0] },
    },
  ],
}));

const userTaskOption = computed(() => ({
  tooltip: {
    trigger: "axis",
    backgroundColor: "rgba(76, 52, 26, 0.92)",
    borderWidth: 0,
    textStyle: { color: "#fffdf8" },
  },
  grid: { left: 48, right: 20, top: 20, bottom: 48 },
  xAxis: { type: "category", data: (props.data?.top_users_by_tasks || []).map((item) => item.name), axisLabel: { interval: 0, rotate: 18 } },
  yAxis: { type: "value" },
  series: [
    {
      type: "bar",
      data: (props.data?.top_users_by_tasks || []).map((item) => item.count),
      itemStyle: { color: "#13c2c2", borderRadius: [8, 8, 0, 0] },
    },
  ],
}));

const userCreditOption = computed(() => ({
  tooltip: {
    trigger: "axis",
    backgroundColor: "rgba(76, 52, 26, 0.92)",
    borderWidth: 0,
    textStyle: { color: "#fffdf8" },
  },
  grid: { left: 48, right: 20, top: 20, bottom: 48 },
  xAxis: { type: "category", data: (props.data?.top_users_by_credit || []).map((item) => item.name), axisLabel: { interval: 0, rotate: 18 } },
  yAxis: { type: "value" },
  series: [
    {
      type: "bar",
      data: (props.data?.top_users_by_credit || []).map((item) => item.credit_cost),
      itemStyle: { color: "#fa8c16", borderRadius: [8, 8, 0, 0] },
    },
  ],
}));

function getRawValue(data: unknown) {
  if (!data || typeof data !== "object") return "";
  return "rawValue" in data && typeof data.rawValue === "string" ? data.rawValue : "";
}

function handleStatusClick(params: { data?: unknown }) {
  const rawValue = getRawValue(params.data);
  if (rawValue) emit("filter-click", { type: "status", value: rawValue });
}

function handleModeClick(params: { data?: unknown }) {
  const rawValue = getRawValue(params.data);
  if (rawValue) emit("filter-click", { type: "mode", value: rawValue });
}

function handleSourceClick(params: { data?: unknown }) {
  const rawValue = getRawValue(params.data);
  if (rawValue) emit("filter-click", { type: "source", value: rawValue });
}

function handleModelClick(params: { dataIndex?: number }) {
  const item = props.data?.model_breakdown[params.dataIndex || 0];
  if (item) emit("filter-click", { type: "model", value: item.name });
}

function handleUserTaskClick(params: { dataIndex?: number }) {
  const item = props.data?.top_users_by_tasks[params.dataIndex || 0];
  if (item) emit("filter-click", { type: "user", value: item.name });
}

function handleUserCreditClick(params: { dataIndex?: number }) {
  const item = props.data?.top_users_by_credit[params.dataIndex || 0];
  if (item) emit("filter-click", { type: "user", value: item.name });
}
</script>

<template>
  <a-spin :spinning="loading">
    <div v-if="hasBreakdownData" class="breakdown-grid">
      <div class="breakdown-card warm-card motion-card-lift motion-fade-up" style="--motion-delay: 220ms">
        <div class="breakdown-head">
          <div>
            <div class="breakdown-title">任务状态占比</div>
            <div class="breakdown-desc">查看整体结果健康度。</div>
          </div>
          <div class="breakdown-badge">饼图</div>
        </div>
        <VChart class="breakdown-chart" :option="statusPieOption" autoresize @click="handleStatusClick" />
      </div>
      <div class="breakdown-card warm-card motion-card-lift motion-fade-up" style="--motion-delay: 260ms">
        <div class="breakdown-head">
          <div>
            <div class="breakdown-title">来源分布（Web/App）</div>
            <div class="breakdown-desc">区分不同端的任务占比和消耗情况。</div>
          </div>
          <div class="breakdown-badge">饼图</div>
        </div>
        <VChart class="breakdown-chart" :option="sourcePieOption" autoresize @click="handleSourceClick" />
      </div>
      <div class="breakdown-card warm-card motion-card-lift motion-fade-up" style="--motion-delay: 300ms">
        <div class="breakdown-head">
          <div>
            <div class="breakdown-title">任务类型占比</div>
            <div class="breakdown-desc">区分生图、局部重绘和提示词反推的占用比例。</div>
          </div>
          <div class="breakdown-badge">饼图</div>
        </div>
        <VChart class="breakdown-chart" :option="modePieOption" autoresize @click="handleModeClick" />
      </div>
      <div class="breakdown-card warm-card motion-card-lift motion-fade-up" style="--motion-delay: 340ms">
        <div class="breakdown-head">
          <div>
            <div class="breakdown-title">模型使用 Top</div>
            <div class="breakdown-desc">了解当前最常被使用的模型。</div>
          </div>
          <div class="breakdown-badge">排行</div>
        </div>
        <VChart class="breakdown-chart" :option="modelBarOption" autoresize @click="handleModelClick" />
      </div>
      <div class="breakdown-card warm-card motion-card-lift motion-fade-up" style="--motion-delay: 380ms">
        <div class="breakdown-head">
          <div>
            <div class="breakdown-title">用户生成次数 Top</div>
            <div class="breakdown-desc">定位高频使用用户。</div>
          </div>
          <div class="breakdown-badge">排行</div>
        </div>
        <VChart class="breakdown-chart" :option="userTaskOption" autoresize @click="handleUserTaskClick" />
      </div>
      <div class="breakdown-card warm-card breakdown-card-wide motion-card-lift motion-fade-up" style="--motion-delay: 420ms">
        <div class="breakdown-head">
          <div>
            <div class="breakdown-title">用户消耗积分 Top</div>
            <div class="breakdown-desc">从消耗角度观察重点用户。</div>
          </div>
          <div class="breakdown-badge">排行</div>
        </div>
        <VChart class="breakdown-chart" :option="userCreditOption" autoresize @click="handleUserCreditClick" />
      </div>
    </div>
    <div v-else class="breakdown-empty warm-card motion-fade-up" style="--motion-delay: 220ms">
      <a-empty class="warm-empty" description="当前筛选条件下暂无分布数据">
        <template #description>
          <div class="empty-title">当前筛选条件下暂无分布数据</div>
          <div class="empty-desc">当有任务、积分或用户数据时，这里会自动展示占比和排行图。</div>
        </template>
      </a-empty>
    </div>
  </a-spin>
</template>

<style scoped lang="scss">
.breakdown-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.breakdown-empty {
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px 20px;
  background:
    radial-gradient(circle at top right, rgba(255, 208, 109, 0.16), transparent 34%),
    linear-gradient(180deg, #fffaf0 0%, #fffefb 100%);
}

.breakdown-card {
  min-height: 320px;
  padding: 18px 20px 14px;
  overflow: hidden;
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 24px 42px rgba(236, 185, 88, 0.16);
    border-color: rgba(241, 210, 154, 0.92);
  }
}

.breakdown-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}

.breakdown-card-wide {
  grid-column: span 2;
}

.breakdown-title {
  font-size: 14px;
  font-weight: 700;
  color: #5d4526;
}

.breakdown-desc {
  margin-top: 4px;
  color: #9a805b;
  font-size: 12px;
  line-height: 1.5;
}

.breakdown-badge {
  flex-shrink: 0;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(255, 245, 223, 0.9);
  color: #a07d49;
  font-size: 11px;
  font-weight: 700;
}

.breakdown-chart {
  height: 260px;
}

.empty-title {
  color: #5d4526;
  font-size: 15px;
  font-weight: 700;
}

.empty-desc {
  margin-top: 6px;
  color: #9a805b;
  font-size: 12px;
}

@media (max-width: 900px) {
  .breakdown-grid {
    grid-template-columns: 1fr;
  }

  .breakdown-card-wide {
    grid-column: span 1;
  }

  .breakdown-card {
    padding: 16px;
  }

  .breakdown-head {
    flex-direction: column;
  }
}
</style>
