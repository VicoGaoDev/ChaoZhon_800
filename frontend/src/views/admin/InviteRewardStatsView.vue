<script setup lang="ts">
import { onMounted, ref } from "vue";
import { GiftOutlined, ReloadOutlined, ShareAltOutlined, TeamOutlined, ThunderboltOutlined } from "@ant-design/icons-vue";
import { message } from "ant-design-vue";
import dayjs from "dayjs";

import { getAdminInviteRewardDashboard, getAdminInviteRewardUserDetail } from "@/api/admin";
import type { AdminInviteRewardDashboard, AdminInviteRewardUserDetail, AdminInviteRewardUserItem } from "@/types";

const loading = ref(false);
const detailLoading = ref(false);
const detailOpen = ref(false);
const dashboard = ref<AdminInviteRewardDashboard>({
  summary: {
    total_referrals: 0,
    rewarded_referrers: 0,
    rewarded_invitees: 0,
    reward_grant_count: 0,
    source_credits: 0,
    reward_credits: 0,
    payment_reward_count: 0,
    redeem_reward_count: 0,
  },
  users: [],
  recent_logs: [],
});
const userDetail = ref<AdminInviteRewardUserDetail | null>(null);

const userColumns = [
  { title: "邀请人", key: "user", width: "22%" },
  { title: "邀请码", dataIndex: "invite_code", width: 120 },
  { title: "推荐用户", dataIndex: "total_referrals", width: 100 },
  { title: "奖励用户", dataIndex: "rewarded_invitees", width: 100 },
  { title: "奖励次数", dataIndex: "reward_grant_count", width: 100 },
  { title: "被邀到账积分", dataIndex: "source_credits", width: 130 },
  { title: "奖励积分", dataIndex: "reward_credits", width: 110 },
  { title: "最近奖励", dataIndex: "last_reward_at", width: 170 },
  { title: "操作", key: "action", width: 96, fixed: "right" as const },
];

const logColumns = [
  { title: "邀请人", dataIndex: "referrer_username", width: 130 },
  { title: "被邀请用户", dataIndex: "invitee_username", width: 140 },
  { title: "来源", dataIndex: "source_type", width: 100 },
  { title: "到账积分", dataIndex: "source_credits", width: 100 },
  { title: "奖励积分", dataIndex: "reward_credits", width: 100 },
  { title: "次数", dataIndex: "reward_index", width: 80 },
  { title: "来源编号", dataIndex: "source_id", ellipsis: true },
  { title: "时间", dataIndex: "created_at", width: 170 },
];

const detailReferralColumns = [
  { title: "被邀请用户", key: "user", width: "28%" },
  { title: "奖励次数", dataIndex: "reward_count", width: 100 },
  { title: "奖励积分", dataIndex: "reward_credits", width: 100 },
  { title: "最近奖励", dataIndex: "last_reward_at", width: 170 },
  { title: "注册时间", dataIndex: "registered_at", width: 170 },
];

const detailLogColumns = [
  { title: "被邀请用户", dataIndex: "invitee_username", width: 140 },
  { title: "来源", dataIndex: "source_type", width: 100 },
  { title: "到账积分", dataIndex: "source_credits", width: 100 },
  { title: "奖励积分", dataIndex: "reward_credits", width: 100 },
  { title: "次数", dataIndex: "reward_index", width: 80 },
  { title: "来源编号", dataIndex: "source_id", ellipsis: true },
  { title: "时间", dataIndex: "created_at", width: 170 },
];

function formatTime(value?: string | null) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "-";
}

function sourceTypeLabel(value: string) {
  if (value === "payment") return "在线购买";
  if (value === "redeem") return "兑换码";
  return value || "-";
}

async function load() {
  loading.value = true;
  try {
    dashboard.value = await getAdminInviteRewardDashboard();
  } catch (err: any) {
    message.error(err.response?.data?.detail || "获取邀请统计失败");
  } finally {
    loading.value = false;
  }
}

async function openUserDetail(record: AdminInviteRewardUserItem) {
  detailOpen.value = true;
  detailLoading.value = true;
  userDetail.value = null;
  try {
    userDetail.value = await getAdminInviteRewardUserDetail(record.user_id);
  } catch (err: any) {
    message.error(err.response?.data?.detail || "获取用户邀请详情失败");
  } finally {
    detailLoading.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<template>
  <div class="warm-page motion-page-enter admin-invite-page">
    <div class="warm-page-header motion-fade-up" style="--motion-delay: 40ms">
      <div class="warm-page-heading">
        <div class="warm-page-icon">
          <ShareAltOutlined />
        </div>
        <div>
          <div class="warm-page-title">邀请奖励统计</div>
          <div class="warm-page-desc">统计所有用户的邀请注册与奖励发放情况。</div>
        </div>
      </div>
      <a-button class="warm-secondary-btn" :loading="loading" @click="load">
        <template #icon><ReloadOutlined /></template>
        刷新
      </a-button>
    </div>

    <a-spin :spinning="loading">
      <div class="admin-invite-body">
        <div class="stats-grid motion-fade-up" style="--motion-delay: 120ms">
          <div class="warm-card stat-card motion-card-lift"><TeamOutlined /><strong>{{ dashboard.summary.total_referrals }}</strong><span>推荐注册用户</span></div>
          <div class="warm-card stat-card motion-card-lift"><ShareAltOutlined /><strong>{{ dashboard.summary.rewarded_referrers }}</strong><span>获得奖励邀请人</span></div>
          <div class="warm-card stat-card motion-card-lift"><GiftOutlined /><strong>{{ dashboard.summary.reward_grant_count }}</strong><span>奖励发放次数</span></div>
          <div class="warm-card stat-card motion-card-lift"><ThunderboltOutlined /><strong>{{ dashboard.summary.reward_credits }}</strong><span>累计奖励积分</span></div>
        </div>

        <div class="stats-grid secondary motion-fade-up" style="--motion-delay: 160ms">
          <div class="warm-card mini-stat-card motion-card-lift"><span>被邀到账积分</span><strong>{{ dashboard.summary.source_credits }}</strong></div>
          <div class="warm-card mini-stat-card motion-card-lift"><span>已奖励被邀用户</span><strong>{{ dashboard.summary.rewarded_invitees }}</strong></div>
          <div class="warm-card mini-stat-card motion-card-lift"><span>购买奖励次数</span><strong>{{ dashboard.summary.payment_reward_count }}</strong></div>
          <div class="warm-card mini-stat-card motion-card-lift"><span>兑换奖励次数</span><strong>{{ dashboard.summary.redeem_reward_count }}</strong></div>
        </div>

        <div class="warm-card warm-table-card motion-fade-up motion-card-lift" style="--motion-delay: 200ms">
          <div class="section-title">邀请人排行</div>
          <a-table :columns="userColumns" :data-source="dashboard.users" row-key="user_id" :pagination="{ pageSize: 20 }" :scroll="{ x: 980 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'user'">
                <div class="user-cell"><strong>{{ record.username }}</strong><span>{{ record.email || record.user_id }}</span></div>
              </template>
              <template v-else-if="column.dataIndex === 'last_reward_at'">
                {{ formatTime(record.last_reward_at) }}
              </template>
              <template v-else-if="column.key === 'action'">
                <a-button type="link" class="detail-link-btn" @click="openUserDetail(record)">查看详情</a-button>
              </template>
            </template>
          </a-table>
        </div>

        <div class="warm-card warm-table-card motion-fade-up motion-card-lift" style="--motion-delay: 240ms">
          <div class="section-title">最近奖励记录</div>
          <a-table :columns="logColumns" :data-source="dashboard.recent_logs" row-key="id" :pagination="{ pageSize: 20 }" :scroll="{ x: 980 }">
            <template #bodyCell="{ column, record }">
              <template v-if="column.dataIndex === 'source_type'">
                <a-tag class="warm-tag">{{ sourceTypeLabel(record.source_type) }}</a-tag>
              </template>
              <template v-else-if="column.dataIndex === 'reward_index'">
                第 {{ record.reward_index }} 次
              </template>
              <template v-else-if="column.dataIndex === 'created_at'">
                {{ formatTime(record.created_at) }}
              </template>
            </template>
          </a-table>
        </div>
      </div>
    </a-spin>

    <a-drawer v-model:open="detailOpen" width="920" :title="userDetail ? `${userDetail.user.username} 的邀请数据` : '邀请数据详情'" :destroy-on-close="true">
      <a-spin :spinning="detailLoading">
        <template v-if="userDetail">
          <div class="detail-user-card">
            <div><strong>{{ userDetail.user.username }}</strong><span>{{ userDetail.user.email || userDetail.user.user_id }}</span></div>
            <a-tag class="warm-tag">{{ userDetail.user.invite_code || "暂无邀请码" }}</a-tag>
          </div>

          <div class="stats-grid secondary detail-stats">
            <div class="warm-card mini-stat-card"><span>推荐用户</span><strong>{{ userDetail.summary.total_referrals }}</strong></div>
            <div class="warm-card mini-stat-card"><span>奖励用户</span><strong>{{ userDetail.summary.rewarded_invitees }}</strong></div>
            <div class="warm-card mini-stat-card"><span>奖励次数</span><strong>{{ userDetail.summary.reward_grant_count }}</strong></div>
            <div class="warm-card mini-stat-card"><span>奖励积分</span><strong>{{ userDetail.summary.reward_credits }}</strong></div>
          </div>

          <div class="detail-section">
            <div class="section-title">推荐用户</div>
            <a-table :columns="detailReferralColumns" :data-source="userDetail.referrals" row-key="user_id" :pagination="{ pageSize: 10 }" :scroll="{ x: 760 }">
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'user'">
                  <div class="user-cell"><strong>{{ record.username }}</strong><span>{{ record.email || record.user_id }}</span></div>
                </template>
                <template v-else-if="column.dataIndex === 'last_reward_at'">
                  {{ formatTime(record.last_reward_at) }}
                </template>
                <template v-else-if="column.dataIndex === 'registered_at'">
                  {{ formatTime(record.registered_at) }}
                </template>
              </template>
            </a-table>
          </div>

          <div class="detail-section">
            <div class="section-title">奖励流水</div>
            <a-table :columns="detailLogColumns" :data-source="userDetail.reward_logs" row-key="id" :pagination="{ pageSize: 10 }" :scroll="{ x: 860 }">
              <template #bodyCell="{ column, record }">
                <template v-if="column.dataIndex === 'source_type'">
                  <a-tag class="warm-tag">{{ sourceTypeLabel(record.source_type) }}</a-tag>
                </template>
                <template v-else-if="column.dataIndex === 'reward_index'">
                  第 {{ record.reward_index }} 次
                </template>
                <template v-else-if="column.dataIndex === 'created_at'">
                  {{ formatTime(record.created_at) }}
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
.admin-invite-page,
.admin-invite-body,
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
