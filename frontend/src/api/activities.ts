import client from "./client";
import type { ActivityItem, ActivityListResponse, ActivityPayload, ActivityStatus } from "@/types";

export function getActiveActivity(): Promise<ActivityItem | null> {
  return client.get("/activities/active");
}

export function listAdminActivities(page = 1, pageSize = 20): Promise<ActivityListResponse> {
  return client.get("/admin/activities", {
    params: { page, page_size: pageSize },
  });
}

export function createAdminActivity(payload: ActivityPayload): Promise<ActivityItem> {
  return client.post("/admin/activities", payload);
}

export function updateAdminActivity(activityId: string, payload: ActivityPayload): Promise<ActivityItem> {
  return client.put(`/admin/activities/${activityId}`, payload);
}

export function updateAdminActivityStatus(activityId: string, status: ActivityStatus): Promise<ActivityItem> {
  return client.patch(`/admin/activities/${activityId}/status`, { status });
}

export function deleteAdminActivity(activityId: string): Promise<void> {
  return client.delete(`/admin/activities/${activityId}`);
}
