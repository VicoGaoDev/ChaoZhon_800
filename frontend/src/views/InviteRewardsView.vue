<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import {
  CopyOutlined,
  DownloadOutlined,
  GiftOutlined,
  QrcodeOutlined,
  ShareAltOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  UserAddOutlined,
  CheckCircleOutlined,
  RiseOutlined,
} from "@ant-design/icons-vue";
import { message } from "ant-design-vue";
import QRCode from "qrcode";
import dayjs from "dayjs";

import {
  getInviteRewardLogs,
  getInviteRewardOverview,
  getInviteRewardReferrals,
} from "@/api/inviteRewards";
import type {
  InviteRewardLogItem,
  InviteRewardOverviewResponse,
  InviteRewardReferralItem,
} from "@/types";

const loading = ref(false);
const qrCodeDataUrl = ref("");
const overview = ref<InviteRewardOverviewResponse>({
  invite_code: "",
  invite_link: "",
  reward_rate: 15,
  max_reward_count: 3,
  summary: {
    total_referrals: 0,
    today_referrals: 0,
    rewarded_invitees: 0,
    reward_grant_count: 0,
    total_reward_credits: 0,
    today_reward_credits: 0,
  },
});
const referrals = ref<InviteRewardReferralItem[]>([]);
const rewardLogs = ref<InviteRewardLogItem[]>([]);

const referralColumns = [
  { title: "用户", key: "user", width: "26%" },
  { title: "已奖励次数", dataIndex: "reward_count", width: 120 },
  { title: "累计奖励积分", dataIndex: "total_reward_credits", width: 140 },
  { title: "最近奖励时间", dataIndex: "last_reward_at", width: 170 },
  { title: "注册时间", dataIndex: "registered_at", width: 170 },
];

const rewardLogColumns = [
  { title: "用户", key: "user", width: "24%" },
  { title: "来源", dataIndex: "source_type", width: 100 },
  { title: "到账积分", dataIndex: "source_credits", width: 100 },
  { title: "奖励积分", dataIndex: "reward_credits", width: 100 },
  { title: "次数", dataIndex: "reward_index", width: 90 },
  { title: "来源编号", dataIndex: "source_id", ellipsis: true },
  { title: "奖励时间", dataIndex: "created_at", width: 170 },
];

function formatTime(value?: string | null) {
  return value ? dayjs(value).format("YYYY-MM-DD HH:mm:ss") : "-";
}

function sourceTypeLabel(value: string) {
  if (value === "payment") return "在线购买";
  if (value === "redeem") return "兑换码";
  return value || "-";
}

async function copyText(text: string, successText: string) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    message.success(successText);
  } catch {
    message.error("复制失败，请重试");
  }
}

async function refreshQrCode(link: string) {
  qrCodeDataUrl.value = "";
  if (!link) return;
  qrCodeDataUrl.value = await QRCode.toDataURL(link, {
    width: 192,
    margin: 1,
    errorCorrectionLevel: "M",
  });
}

function downloadQrCode() {
  if (!qrCodeDataUrl.value) {
    message.warning("二维码还未生成，请稍后重试");
    return;
  }
  const link = document.createElement("a");
  link.href = qrCodeDataUrl.value;
  link.download = `invite-${overview.value.invite_code || "qrcode"}.png`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

async function loadData() {
  loading.value = true;
  try {
    const [overviewRes, referralsRes, logsRes] = await Promise.all([
      getInviteRewardOverview(),
      getInviteRewardReferrals(),
      getInviteRewardLogs(),
    ]);
    overview.value = overviewRes;
    referrals.value = referralsRes.items;
    rewardLogs.value = logsRes.items;
  } catch (err: any) {
    message.error(err.response?.data?.detail || "获取邀请奖励数据失败");
  } finally {
    loading.value = false;
  }
}

watch(
  () => overview.value.invite_link,
  (link) => {
    void refreshQrCode(link);
  },
);

onMounted(() => {
  void loadData();
});
</script>

<template>
  <div class="warm-page motion-page-enter invite-page">
    <div class="warm-page-header motion-fade-up" style="--motion-delay: 40ms">
      <div class="warm-page-heading">
        <div class="warm-page-icon">
          <ShareAltOutlined />
        </div>
        <div>
          <div class="warm-page-title">邀请奖励计划</div>
          <div class="warm-page-desc">分享专属邀请链接，推荐用户在线购买积分后获得积分奖励。</div>
        </div>
      </div>
    </div>

    <a-spin :spinning="loading">
      <div class="invite-page-body">
        <div class="warm-card invite-main-card motion-fade-up motion-card-lift" style="--motion-delay: 120ms">
          <div class="invite-rule-banner">
            被推荐用户前 {{ overview.max_reward_count }} 次在线购买积分时，邀请人每次获得
            <strong class="invite-rule-rate">{{ overview.reward_rate }}%</strong>
            积分奖励，立即到账。
          </div>

          <div class="invite-main-layout">
            <div class="invite-main-left">
              <div class="invite-guide">
                <div class="section-title">如何使用</div>
                <ol class="invite-guide-steps">
                  <li>复制邀请链接或下载邀请二维码发给好友，也可直接分享邀请码。</li>
                  <li>好友通过你的链接注册后，会自动建立邀请关系。</li>
                  <li>好友在线购买积分时，你会按规则获得奖励积分。</li>
                </ol>
              </div>

              <div class="invite-summary-grid">
                <div class="invite-summary-item">
                  <div class="invite-summary-icon"><TeamOutlined /></div>
                  <span>推荐好友</span>
                  <strong>{{ overview.summary.total_referrals }}</strong>
                </div>
                <div class="invite-summary-item">
                  <div class="invite-summary-icon"><CheckCircleOutlined /></div>
                  <span>已奖励用户</span>
                  <strong>{{ overview.summary.rewarded_invitees }}</strong>
                </div>
                <div class="invite-summary-item">
                  <div class="invite-summary-icon"><UserAddOutlined /></div>
                  <span>今日推荐</span>
                  <strong>{{ overview.summary.today_referrals }}</strong>
                </div>
                <div class="invite-summary-item">
                  <div class="invite-summary-icon"><GiftOutlined /></div>
                  <span>奖励次数</span>
                  <strong>{{ overview.summary.reward_grant_count }}</strong>
                </div>
                <div class="invite-summary-item">
                  <div class="invite-summary-icon"><ThunderboltOutlined /></div>
                  <span>累计奖励积分</span>
                  <strong>{{ overview.summary.total_reward_credits }}</strong>
                </div>
                <div class="invite-summary-item">
                  <div class="invite-summary-icon"><RiseOutlined /></div>
                  <span>今日奖励积分</span>
                  <strong>{{ overview.summary.today_reward_credits }}</strong>
                </div>
              </div>
            </div>

            <div class="invite-main-right">
              <div class="invite-field">
                <span class="invite-field-label">邀请码</span>
                <div class="invite-field-value">
                  <code>{{ overview.invite_code || "-" }}</code>
                  <a-button type="link" class="invite-copy-btn" @click="copyText(overview.invite_code, '邀请码已复制')">
                    <template #icon><CopyOutlined /></template>
                    复制
                  </a-button>
                </div>
              </div>

              <div class="invite-field">
                <span class="invite-field-label">邀请链接</span>
                <div class="invite-field-value invite-link-value">
                  <span>{{ overview.invite_link || "-" }}</span>
                  <a-button type="link" class="invite-copy-btn" @click="copyText(overview.invite_link, '邀请链接已复制')">
                    <template #icon><CopyOutlined /></template>
                    复制
                  </a-button>
                </div>
              </div>

              <div class="invite-qr-block">
                <div class="invite-qr-head">
                  <QrcodeOutlined />
                  <span>邀请二维码</span>
                </div>
                <div class="invite-qr-wrap">
                  <img v-if="qrCodeDataUrl" :src="qrCodeDataUrl" alt="邀请二维码">
                  <div v-else class="invite-qr-placeholder">生成中...</div>
                </div>
                <a-button type="link" class="invite-download-btn" :disabled="!qrCodeDataUrl" @click="downloadQrCode">
                  <template #icon><DownloadOutlined /></template>
                  下载二维码
                </a-button>
              </div>
            </div>
          </div>
        </div>

        <div class="warm-card invite-data-card motion-fade-up motion-card-lift" style="--motion-delay: 200ms">
          <div class="invite-data-section">
            <div class="section-title">推荐好友</div>
            <a-table :columns="referralColumns" :data-source="referrals" row-key="user_id" :pagination="{ pageSize: 10 }" :scroll="{ x: 860 }">
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'user'">
                  <div class="invite-user-cell">
                    <strong>{{ record.username }}</strong>
                    <span>{{ record.email_masked }}</span>
                  </div>
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

          <div class="invite-data-section">
            <div class="section-title">奖励记录</div>
            <a-table :columns="rewardLogColumns" :data-source="rewardLogs" row-key="id" :pagination="{ pageSize: 10 }" :scroll="{ x: 980 }">
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'user'">
                  <div class="invite-user-cell">
                    <strong>{{ record.invitee_username }}</strong>
                    <span>{{ record.invitee_email_masked }}</span>
                  </div>
                </template>
                <template v-else-if="column.dataIndex === 'source_type'">
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
      </div>
    </a-spin>
  </div>
</template>

<style scoped lang="scss">
.invite-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-inline: 14px;
}

.invite-page-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.invite-main-card,
.invite-data-card {
  padding: 22px 24px 24px;
}

.section-title {
  margin-bottom: 14px;
  color: var(--theme-title);
  font-size: 16px;
  font-weight: 800;
}

.invite-rule-banner {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--theme-pill-bg-strong);
  color: var(--theme-accent-text);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.6;
}

.invite-rule-rate {
  margin-inline: 2px;
  font-size: 24px;
}

.invite-main-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.9fr);
  gap: 20px;
  margin-top: 18px;
}

.invite-main-left,
.invite-main-right,
.invite-data-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.invite-guide {
  padding: 16px;
  border: 1px solid var(--theme-border);
  border-radius: 16px;
  background: var(--theme-bg-elevated, rgba(255, 255, 255, 0.72));
}

.invite-guide-steps {
  margin: 0;
  padding-left: 18px;
  color: var(--theme-text);
  line-height: 1.75;
}

.invite-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.invite-summary-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 16px;
  background: var(--theme-bg-elevated, rgba(255, 255, 255, 0.72));
  border: 1px solid var(--theme-border);

  span {
    color: var(--theme-text-secondary);
    font-weight: 700;
  }

  strong {
    color: var(--theme-title);
    font-size: 28px;
    line-height: 1;
  }
}

.invite-summary-icon,
.invite-qr-head {
  color: var(--theme-accent-text);
}

.invite-field {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--theme-border);
  background: var(--theme-bg-elevated, rgba(255, 255, 255, 0.72));
}

.invite-field-label {
  color: var(--theme-text-secondary);
  font-weight: 700;
}

.invite-field-value {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--theme-title);

  code {
    font-size: 18px;
    font-weight: 800;
  }
}

.invite-link-value span {
  word-break: break-all;
}

.invite-qr-block {
  display: flex;
  flex-direction: column;
  gap: 14px;
  align-items: center;
  padding: 18px;
  border-radius: 16px;
  border: 1px solid var(--theme-border);
  background: var(--theme-bg-elevated, rgba(255, 255, 255, 0.72));
}

.invite-qr-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 220px;
  height: 220px;
  border-radius: 20px;
  background: #fff;

  img {
    width: 192px;
    height: 192px;
  }
}

.invite-qr-placeholder {
  color: var(--theme-text-secondary);
}

.invite-user-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;

  strong {
    color: var(--theme-title);
  }

  span {
    color: var(--theme-text-secondary);
    font-size: 12px;
  }
}

@media (max-width: 960px) {
  .invite-main-layout {
    grid-template-columns: 1fr;
  }

  .invite-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .invite-main-card,
  .invite-data-card {
    padding: 18px;
  }

  .invite-summary-grid {
    grid-template-columns: 1fr;
  }

  .invite-field-value {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
