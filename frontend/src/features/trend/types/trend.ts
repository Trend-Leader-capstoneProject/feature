export type TrendCategoryCode =
  | "FASHION"
  | "FOOD"
  | "IT_DIGITAL"
  | "ENTERTAINMENT"
  | "BEAUTY"
  | "GAME";

export type TrendSourcePlatform =
  | "GOOGLE"
  | "YOUTUBE"
  | "SNS"
  | "ETC";

export interface TrendCategoryParent {
  category_id: number;
  category_code: TrendCategoryCode | null;
  category_name: string;
}

export interface TrendCategoryItem {
  category_id: number;
  category_name: string;
  parent: TrendCategoryParent;
}

export interface TrendLatestSource {
  source_id: number;
  platform: TrendSourcePlatform;
  source_title: string | null;
  source_url: string;
}

export interface TrendListItem {
  trend_id: number;
  title: string;
  summary: string | null;
  thumbnail_url: string | null;

  /*
   * API에서는 UTC-aware ISO 8601 문자열을 반환한다.
   * 예: 2026-10-01T09:00:00Z
   */
  last_collected_at: string;

  categories: TrendCategoryItem[];
  latest_source: TrendLatestSource | null;
}

export interface TrendListData {
  items: TrendListItem[];
  next_cursor: string | null;
  has_next: boolean;
}

export interface GetTrendsParams {
  cursor?: string;
  limit?: number;
  category_id?: number;
}

export type TrendListErrorReason =
  | "INVALID_CURSOR"
  | "CATEGORY_NOT_AVAILABLE"
  | "CATEGORY_NOT_FOUND";

export interface TrendListErrorData {
  reason: TrendListErrorReason;
}
