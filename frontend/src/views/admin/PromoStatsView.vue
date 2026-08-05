<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  GiftOutlined,
  ReloadOutlined,
  ShareAltOutlined,
  TeamOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons-vue";
import { message } from "ant-design-vue";
import dayjs from "dayjs";

import { getAdminPromoStatsDashboard, getAdminPromoStatsUserDetail } from "@/api/admin";
import type {
  AdminPromoStatsDashboard,
  AdminPromoStatsUserItem,
  AdminUserPromoDashboard,
} from "@/types";

const loading = ref(false);
const detailLoading = ref(false);
const detailOpen = ref(false);
const dashboard = ref<AdminPromoStatsDashboard>({
  summary: {
    total_referrals: 0,
    active_promoters: 0,
    total_promo_codes: 0,
    used_promo_codes: 0,
    whitelisted_users: 0,
    reward_credits: 0,
    purchase_count: 0,
    purchase_credits: 0,
    redeem_count: 0,
    redeem_credits: 0,
  },
  users: [],
  recent_referrals: [],
});
const userDetail = ref<AdminUserPromoDashboard | null>(null);

const userColumns = [
  { title: "推广人", key: "user", width: "22%" },
  { title: "推广码数", dataIndex: "promo_code_count", width: 100 },
  { title: "已使用码", dataIndex: "used_code_count", width: 100 },
  { title: "推广注册", dataIndex: "total_referrals", width: 100 },
  { title: "注册奖励积分", dataIndex: "reward_credits", width: 120 },
  { title: "推广用户购买积分", dataIndex: "purchase_credits", width: 140 },
  { title: "推广用户兑换积分", dataIndex: "redeem_credits", width: 140 },
  { title: "最近推广", dataIndex: "last_referral_at", width: 170 },
  { title: "操作", key: "action", width: 96, fixed: "right" as const },
];

const referralColumns = [
  { title: "推广人", dataIndex: "promoter_username", width: 130 },
  { title: "推广用户", dataIndex: "invitee_username", width: 140 },
  { title: "推广码", dataIndex: "promo_code", width: 120 },
  { title: "平台", dataIndex: "platform_name", width: 140 },
  { title: "注册奖励积分", dataIndex: "reward_credits", width: 120 },
  { title: "注册时间", dataIndex: "registered_at", width: 170 },
];

const detailPromoColumns = [
  { title: "推广码", dataIndex: "code", width: 140 },
  { title: "平台", dataIndex: "platform_name", width: 160 },
  { title: "使用人数", dataIndex: "referral_count", width: 100 },
  { title: "状态", dataIndex: "status", width: 100 },
  { title: "创建时间", dataIndex: "created_at", width: 170 },
];

const detailReferralColumns = [
  { title: "用户", key: "user", width: "24%" },
  { title: "推广码", dataIndex: "promo_code", width: 120 },
  { title: "平台", dataIndex: "platform_name", width: 140 },
  { title: "奖励积分", dataIndex: "reward_credits", width: 100 },
  { title: "注册时间", dataIndex: "registered_at", width: 170 },
];

const detailActivityColumns = [
  { title: "用户", key: "user", width: "24%" },
  { title: "类型", dataIndex: "activity_type", width: 110 },
  { title: "积分", dataIndex: "credits", width: 90 },
  { title: "金额", dataIndex: "amount_yuan", width: 100 },
  { title: "时间", dataIndex: "occurred_at", width: 170 },
];

function formatTime(value?: string | null) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "-";
}

function activityTypeLabel(value: string) {
  if (value === "purchase") return "购买订单";
  if (value === "redeem") return "兑换码兑换";
  return value || "-";
}

function promoActivityRowKey(record: AdminUserPromoDashboard["activities"][number], index: number) {
  return `${record.activity_type}-${record.order_no || record.redeem_key || record.user_id}-${index}`;
}

async function load() {
  loading.value = true;
  try {
    dashboard.value = await getAdminPromoStatsDashboard();
  } catch (err: any) {
    message.error(err.response?.data?.detail || "获取白名单推广统计失败");
  } finally {
    loading.value = false;
  }
}

async function openUserDetail(record: AdminPromoStatsUserItem) {
  detailOpen.value = true;
  detailLoading.value = true;
  userDetail.value = null;
  try {
    userDetail.value = await getAdminPromoStatsUserDetail(record.user_id);
  } catch (err: any) {
    message.error(err.response?.data?.detail || "获取推广详情失败");
  } finally {
    detailLoading.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div class="warm-page motion-page-enter admin-promo-page">
    <div class="warm-page-header motion-fade-up" style="--motion-delay: 40ms">
      <div class="warm-page-heading">
        <div class="warm-page-icon">
          <GiftOutlined />
        </div>
        <div>
          <div class="warm-page-title">白名单推广统计</div>
          <div class="warm-page-desc">统计白名单用户推广码注册、奖励发放与推广用户消费情况。</div>
        </div>
      </div>
      <a-button class="warm-secondary-btn" :loading="loading" @click="load">
        <template #icon><ReloadOutlined /></template>
        刷新
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <div class="admin-promo-body">
        <div class="stats-grid motion-fade-up" style="--motion-delay: 120ms">
          <div class="warm-card stat-card motion-card-lift"><TeamOutlined /><strong>{{ dashboard.summary.total_referrals }}</strong><span>推广注册用户</span></div>
          <div class="warm-card stat-card motion-card-lift"><ShareAltOutlined /><strong>{{ dashboard.summary.active_promoters }}</strong><span>有效推广人</span></div>
          <div class="warm-card stat-card motion-card-lift"><GiftOutlined /><strong>{{ dashboard.summary.total_promo_codes }}</strong><span>推广码总数</span></div>
          <div class="warm-card stat-card motion-card-lift"><ThunderboltOutlined /><strong>{{ dashboard.summary.reward_credits }}</strong><span>注册奖励积分</span></div>
        </div>

        <div class="stats-grid secondary motion-fade-up" style="--motion-delay: 160ms">
          <div class="warm-card mini-stat-card motion-card-lift"><span>已使用推广码</span><strong>{{ dashboard.summary.used_promo_codes }}</strong></div>
          <div class="warm-card mini-stat-card motion-card-lift"><span>白名单用户</span><strong>{{ dashboard.summary.whitelisted_users }}</strong></div>
          <div class="warm-card mini-stat-card motion-card-lift"><span>推广用户购买积分</span><strong>{{ dashboard.summary.purchase_credits }}</strong></div>
          <div class="warm-card mini-stat-card motion-card-lift"><span>推广用户兑换积分</span><strong>{{ dashboard.summary.redeem_credits }}</strong></div>
        </div>

        <div class="warm-card warm-table-card motion-fade-up motion-card-lift" style="--motion-delay: 200ms">
          <div class="section-title">推广人排行</div>
          <a-table :columns="userColumns" :data-source="dashboard.users" row-key="user_id" :pagination="{ pageSize: 20 }" :scroll="{ x: 1100 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'user'">
                <div class="user-cell"><strong>{{ record.username }}</strong><span>{{ record.email || record.user_id }}</span></div>
              </template>
              <template v-else-if="column.dataIndex === 'last_referral_at'">
                {{ formatTime(record.last_referral_at) }}
              </template>
              <template v-else-if="column.key === 'action'">
                <a-button type="link" class="detail-link-btn" @click="openUserDetail(record)">查看详情</a-button>
              </template>
            </template>
          </a-table>
        </div>

        <div class="warm-card warm-table-card motion-fade-up motion-card-lift" style="--motion-delay: 240ms">
          <div class="section-title">最近推广注册</div>
          <a-table :columns="referralColumns" :data-source="dashboard.recent_referrals" row-key="id" :pagination="{ pageSize: 20 }" :scroll="{ x: 900 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.dataIndex === 'registered_at'">
                {{ formatTime(record.registered_at) }}
              </template>
            </template>
          </a-table>
        </div>
      </div>
    </a-spin>

    <a-drawer v-model:open="detailOpen" width="920" :title="userDetail ? `${userDetail.username} 的推广数据` : '推广数据详情'" :destroy-on-close="true">
      <a-spin :spinning="detailLoading">
        <template v-if="userDetail">
          <div class="detail-user-card">
            <div><strong>{{ userDetail.username }}</strong><span>{{ userDetail.user_id }}</span></div>
            <a-tag class="warm-tag">推广注册 {{ userDetail.summary.total_referrals }}</a-tag>
          </div>

          <div class="stats-grid secondary detail-stats">
            <div class="warm-card mini-stat-card"><span>推广注册</span><strong>{{ userDetail.summary.total_referrals }}</strong></div>
            <div class="warm-card mini-stat-card"><span>已使用推广码</span><strong>{{ userDetail.summary.used_code_count }}</strong></div>
            <div class="warm-card mini-stat-card"><span>奖励发放人数</span><strong>{{ userDetail.summary.rewarded_registrations }}</strong></div>
            <div class="warm-card mini-stat-card"><span>推广码数量</span><strong>{{ userDetail.promo_codes.length }}</strong></div>
          </div>

          <div class="detail-section">
            <div class="section-title">推广码列表</div>
            <a-table :columns="detailPromoColumns" :data-source="userDetail.promo_codes" row-key="id" :pagination="{ pageSize: 10 }" :scroll="{ x: 700 }">
              <template #bodyCell="{ column, record }">
                <template v-if="column.dataIndex === 'status'">
                  <a-tag class="warm-tag">{{ record.status === "enabled" ? "启用" : "停用" }}</a-tag>
                </template>
                <template v-else-if="column.dataIndex === 'created_at'">
                  {{ formatTime(record.created_at) }}
                </template>
              </template>
            </a-table>
          </div>

          <div class="detail-section">
            <div class="section-title">推广用户</div>
            <a-table :columns="detailReferralColumns" :data-source="userDetail.referrals" row-key="user_id" :pagination="{ pageSize: 10 }" :scroll="{ x: 760 }">
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'user'">
                  <div class="user-cell"><strong>{{ record.username }}</strong><span>{{ record.email || record.email_masked || record.user_id }}</span></div>
                </template>
                <template v-else-if="column.dataIndex === 'registered_at'">
                  {{ formatTime(record.registered_at) }}
                </template>
              </template>
            </a-table>
          </div>

          <div class="detail-section">
            <div class="section-title">推广用户积分记录</div>
            <a-table :columns="detailActivityColumns" :data-source="userDetail.activities" :row-key="promoActivityRowKey" :pagination="{ pageSize: 10 }" :scroll="{ x: 760 }">
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'user'">
                  <div class="user-cell"><strong>{{ record.username }}</strong><span>{{ record.email_masked || record.user_id }}</span></div>
                </template>
                <template v-else-if="column.dataIndex === 'activity_type'">
                  <a-tag class="warm-tag">{{ activityTypeLabel(record.activity_type) }}</a-tag>
                </template>
                <template v-else-if="column.dataIndex === 'occurred_at'">
                  {{ formatTime(record.occurred_at) }}
                </template>
              </template>
            </a-table>
          </div>
        </template>
      </a-spin>
    </a-drawer>
  </div>
</template>

<style scoped lang="scss">
.admin-promo-page,
.admin-promo-body,
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card,
.mini-stat-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px;

  strong {
    color: var(--theme-title);
    font-size: 28px;
    line-height: 1;
  }

  span {
    color: var(--theme-text-secondary);
    font-weight: 700;
  }
}

.secondary .mini-stat-card strong {
  font-size: 22px;
}

.user-cell,
.detail-user-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-user-card {
  margin-bottom: 16px;
}

.detail-stats {
  margin-bottom: 16px;
}

@media (max-width: 960px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
