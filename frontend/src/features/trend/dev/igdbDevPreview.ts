/** Local-only IGDB review transport. Never uses production Trend APIs or storage. */

import type { TrendCardData } from "../types/trend";

export const IGDB_DEV_PREVIEW_URL = "http://127.0.0.1:58186/preview.json";

export type IgdbDevPreviewResult =
  | { kind: "ready"; trend: TrendCardData }
  | { kind: "empty" };

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function utcTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /(?:Z|\+00:00)$/.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

const OFFICIAL_GAME_URL = /^https:\/\/www\.igdb\.com\/games\/[a-z0-9][a-z0-9-]{0,254}$/;
const GAME_CATEGORIES = ["PC 게임", "모바일 게임", "콘솔 게임"];

export function parseIgdbDevPreview(value: unknown): IgdbDevPreviewResult {
  if (!record(value) || value.publication_status !== "NOT_FOR_PUBLICATION") {
    throw new Error("INVALID_PREVIEW");
  }

  if (value.status === "NO_ELIGIBLE_CANDIDATE") {
    if (Object.keys(value).sort().join(",") !==
        "publication_status,status") {
      throw new Error("INVALID_PREVIEW");
    }
    return { kind: "empty" };
  }

  if (
    value.status !== "VERIFIED_PREVIEW" ||
    typeof value.title !== "string" || !value.title.trim() ||
    typeof value.summary !== "string" || !value.summary.trim() ||
    value.parent_code !== "GAME" ||
    !GAME_CATEGORIES.includes(value.child_name as string) ||
    !Number.isInteger(value.rank) || (value.rank as number) < 1 ||
    (value.rank as number) > 20 ||
    !utcTimestamp(value.observed_at_utc) ||
    !utcTimestamp(value.calculated_at_utc) ||
    typeof value.source_url !== "string" ||
    !OFFICIAL_GAME_URL.test(value.source_url)
  ) {
    throw new Error("INVALID_PREVIEW");
  }

  return {
    kind: "ready",
    trend: {
      title: value.title,
      summary: value.summary,
      thumbnail_url: null,
      last_collected_at: value.observed_at_utc,
      categories: [{
        category_name: value.child_name as string,
        parent: { category_name: "게임" },
      }],
      latest_source: {
        platform: "ETC",
        source_title: "IGDB Visits",
        source_url: value.source_url,
      },
    },
  };
}

export async function fetchIgdbDevPreview(): Promise<IgdbDevPreviewResult> {
  if (!__DEV__) {
    throw new Error("DEV_PREVIEW_DISABLED");
  }
  const response = await fetch(IGDB_DEV_PREVIEW_URL, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error("PREVIEW_UNAVAILABLE");
  }
  const value: unknown = await response.json();
  return parseIgdbDevPreview(value);
}
