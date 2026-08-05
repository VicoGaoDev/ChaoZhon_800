import client from "./client";
import type {
  InviteRewardLogListResponse,
  InviteRewardOverviewResponse,
  InviteRewardReferralListResponse,
} from "@/types";

export function getInviteRewardOverview(): Promise<InviteRewardOverviewResponse> {
  return client.get("/auth/invite-rewards/me");
}

export function getInviteRewardReferrals(): Promise<InviteRewardReferralListResponse> {
  return client.get("/auth/invite-rewards/referrals");
}

export function getInviteRewardLogs(): Promise<InviteRewardLogListResponse> {
  return client.get("/auth/invite-rewards/logs");
}

export function validateInviteCode(code: string): Promise<{ valid: boolean; code: string; platform_name: string }> {
  return client.get("/auth/invite-codes/validate", {
    params: { code },
  });
}
