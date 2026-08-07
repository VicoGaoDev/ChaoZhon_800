<script setup lang="ts">
import { ref, watch } from "vue";
import { message } from "ant-design-vue";
import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons-vue";
import dayjs from "dayjs";
import { getCreditLogs as getAdminCreditLogs } from "@/api/admin";
import type { AdminUser, CreditLog } from "@/types";

const props = defineProps<{
  open: boolean;
  user: AdminUser | null;
}>();

const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
}>();

const loading = ref(false);
const items = ref<CreditLog[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;

const columns = [
  { title: "时间", dataIndex: "created_at", width: 168 },
  { title: "变动", dataIndex: "type", width: 88 },
  { title: "类型", dataIndex: "mode", width: 110 },
  { title: "积分", dataIndex: "amount", width: 100 },
  { title: "说明", dataIndex: "description", ellipsis: true },
  { title: "操作人", dataIndex: "operator_name", width: 100 },
];

function formatTime(value?: string | null) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "-";
}

function directionLabel(record: CreditLog) {
  return record.amount > 0 ? "增加" : "扣减";
}

function modeLabel(mode: CreditLog["mode"]) {
  if (mode === "text_generate") return "文生图";
  if (mode === "image_edit") return "图编辑";
  if (mode === "inpaint") return "局部重绘";
  if (mode === "promptReverse") return "提示词反推";
  if (mode === "promptOptimize") return "提示词优化";
  if (mode === "redeem") return "兑换积分";
  if (mode === "purchase") return "在线购买";
  return "手动调整";
}

async function loadLogs(userId: string) {
  loading.value = true;
  try {
    const res = await getAdminCreditLogs(
      page.value,
      pageSize,
      userId,
    );
    items.value = res.items;
    total.value = res.total;
  } catch {
    message.error("获取积分明细失败");
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.open, props.user?.id] as const,
  ([open, userId]) => {
    if (open && userId) {
      page.value = 1;
      void loadLogs(userId);
    }
  },
);

function handlePageChange(nextPage: number) {
  page.value = nextPage;
  if (props.user?.id) {
    void loadLogs(props.user.id);
  }
}
</script>

<template>
  <a-modal
    :open="open"
    :title="user ? `积分明细 — ${user.username}` : '积分明细'"
    :footer="null"
    :width="860"
    centered
    class="credit-logs-modal"
    @update:open="emit('update:open', $event)"
  >
    <div class="credit-logs-dialog">
      <div v-if="user" class="credit-logs-summary">
        <div class="credit-logs-stat">
          <span>剩余积分</span>
          <strong>{{ user.credits || 0 }}</strong>
        </div>
        <div class="credit-logs-stat">
          <span>已消耗积分</span>
          <strong class="credit-logs-stat-consumed">{{ user.consumed_credits || 0 }}</strong>
        </div>
        <div class="credit-logs-stat">
          <span>明细记录</span>
          <strong>{{ total }}</strong>
        </div>
      </div>

      <div class="credit-logs-table-wrap">
        <a-table
          :columns="columns"
          :data-source="items"
          :loading="loading"
          :pagination="false"
          row-key="id"
          size="small"
          table-layout="fixed"
          :scroll="{ y: 360 }"
          class="credit-logs-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.dataIndex === 'created_at'">
              {{ formatTime(record.created_at) }}
            </template>
            <template v-else-if="column.dataIndex === 'type'">
              <a-tag class="credit-type-tag" :class="record.amount > 0 ? 'credit-type-tag-income' : 'credit-type-tag-expense'">
                {{ directionLabel(record) }}
              </a-tag>
            </template>
            <template v-else-if="column.dataIndex === 'mode'">
              {{ modeLabel(record.mode) }}
            </template>
            <template v-else-if="column.dataIndex === 'amount'">
              <span :class="record.amount > 0 ? 'amount-plus' : 'amount-minus'">
                <ArrowUpOutlined v-if="record.amount > 0" />
                <ArrowDownOutlined v-else />
                {{ record.amount > 0 ? "+" : "" }}{{ record.amount }}
              </span>
            </template>
            <template v-else-if="column.dataIndex === 'operator_name'">
              {{ record.operator_name || "-" }}
            </template>
          </template>
        </a-table>
      </div>

      <div v-if="total > pageSize" class="credit-logs-pagination">
        <a-pagination
          :current="page"
          :total="total"
          :page-size="pageSize"
          show-less-items
          @change="handlePageChange"
        />
      </div>
    </div>
  </a-modal>
</template>

<style scoped lang="scss">
.credit-logs-dialog {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: min(70vh, 560px);
  overflow: hidden;
}

.credit-logs-table-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.credit-logs-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  flex-shrink: 0;
}

.credit-logs-stat {
  padding: 12px;
  border: 1px solid var(--theme-panel-border);
  border-radius: 14px;
  background: var(--theme-panel-bg);

  span {
    display: block;
    color: var(--theme-text-secondary);
    font-size: 12px;
  }

  strong {
    display: block;
    margin-top: 6px;
    color: var(--theme-title);
    font-size: 20px;
  }
}

.credit-logs-stat-consumed {
  color: #cf1322 !important;
}

.credit-logs-table {
  :deep(.ant-table) {
    background: transparent;
    table-layout: fixed;
  }

  :deep(.ant-table-container),
  :deep(.ant-table-content),
  :deep(.ant-table-body) {
    overflow-x: hidden !important;
  }
}

.credit-type-tag {
  border-radius: 999px;
  font-weight: 600;
}

.credit-type-tag-income {
  color: #1f9d63;
  background: #e8f8ef;
  border-color: #b7e4c7;
}

.credit-type-tag-expense {
  color: #d6574b;
  background: #fff1ef;
  border-color: #f0c7c2;
}

.amount-plus {
  color: #1f9d63;
  font-weight: 700;
}

.amount-minus {
  color: #d6574b;
  font-weight: 700;
}

.credit-logs-pagination {
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .credit-logs-summary {
    grid-template-columns: 1fr;
  }
}
</style>
