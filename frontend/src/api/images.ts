import client from "./client";
import type { ImageResult } from "@/types";

const WEBP_PREVIEW_RULE = "imageMogr2/format/webp";
export const REALTIME_IMAGE_PREVIEW_LIMIT_BYTES = 32 * 1024 * 1024;
export const LARGE_IMAGE_PREVIEW_NOTICE = "原图体积较大，暂不支持实时预览，请下载原图查看完整内容";

export function regenerateImage(imageId: number): Promise<any> {
  return client.post(`/images/${imageId}/regenerate`);
}

export function deleteImage(imageId: number): Promise<void> {
  return client.delete(`/images/${imageId}`);
}

export function resolveImageUrl(imageUrl?: string): string {
  if (!imageUrl) return "";
  if (/^(https?:)?\/\//.test(imageUrl) || imageUrl.startsWith("data:") || imageUrl.startsWith("blob:")) {
    return imageUrl;
  }
  const base = import.meta.env.VITE_API_BASE_URL || "";
  return `${base}${imageUrl.startsWith("/") ? imageUrl : `/${imageUrl}`}`;
}

export function resolvePreviewImageUrl(imageUrl?: string): string {
  const resolvedUrl = resolveImageUrl(imageUrl);
  if (!resolvedUrl || resolvedUrl.startsWith("data:") || resolvedUrl.startsWith("blob:")) {
    return resolvedUrl;
  }
  if (resolvedUrl.includes(WEBP_PREVIEW_RULE)) {
    return resolvedUrl;
  }

  const [urlWithoutHash, hash = ""] = resolvedUrl.split("#", 2);
  const separator = urlWithoutHash.includes("?") ? "&" : "?";
  return `${urlWithoutHash}${separator}${WEBP_PREVIEW_RULE}${hash ? `#${hash}` : ""}`;
}

export function exceedsRealtimeImagePreviewLimit(imageSizeBytes?: number | null): boolean {
  return typeof imageSizeBytes === "number" && imageSizeBytes >= REALTIME_IMAGE_PREVIEW_LIMIT_BYTES;
}

export function getDisplayImageUrl(image?: Pick<ImageResult, "thumb_url" | "image_url" | "preview_url">): string {
  return resolvePreviewImageUrl(image?.thumb_url || image?.image_url || image?.preview_url || "");
}

export function getPreviewImageUrl(image?: Pick<ImageResult, "image_url" | "preview_url" | "thumb_url">): string {
  return resolvePreviewImageUrl(image?.image_url || image?.preview_url || image?.thumb_url || "");
}

function buildDownloadFilename(imageId: number, imageUrl: string): string {
  const cleanPath = imageUrl.split("?")[0] || "";
  const suffix = cleanPath.includes(".") ? cleanPath.slice(cleanPath.lastIndexOf(".")) : ".png";
  return `banana_${imageId}${suffix || ".png"}`;
}

export function getDownloadUrl(imageId: number, imageUrl?: string, previewUrl?: string): string {
  if (imageUrl && /^https?:\/\//.test(imageUrl)) {
    return imageUrl;
  }
  if (!imageUrl && previewUrl) {
    return resolveImageUrl(previewUrl);
  }
  const base = import.meta.env.VITE_API_BASE_URL || "";
  return `${base}/api/images/${imageId}/download`;
}
