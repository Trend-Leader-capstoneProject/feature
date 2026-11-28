import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import { useState } from "react";
import { Image, Text, View } from "react-native";

import { borders, radius, spacing, textLineLimits, typography } from "../../../shared/constants";
import type { ColorToken } from "../../../shared/constants";
import type { TrendCategoryCode, TrendCategoryItem, TrendListItem } from "../types/trend";
import { TrendCategoryChips } from "./TrendCategoryChips";
import { TrendSourceSection } from "./TrendSourceSection";

const THUMBNAIL_SIZE = 96;

type CategoryThumbnail = {
  icon: string;
  label: string;
  background: ColorToken;
};

const CATEGORY_THUMBNAILS = new Map<TrendCategoryCode, CategoryThumbnail>([
  ["FASHION", { icon: "👕", label: "패션", background: "backgroundSelected" }],
  ["FOOD", { icon: "🍽️", label: "음식", background: "statusPositiveSubtle" }],
  ["IT_DIGITAL", { icon: "💻", label: "IT/디지털", background: "statusInformationSubtle" }],
  ["ENTERTAINMENT", { icon: "🎬", label: "엔터테인먼트", background: "signalHighlightSubtle" }],
  ["BEAUTY", { icon: "💄", label: "뷰티", background: "statusNegativeSubtle" }],
  ["GAME", { icon: "🎮", label: "게임", background: "backgroundBrandMuted" }],
]);

const DEFAULT_THUMBNAIL: CategoryThumbnail = {
  icon: "↗",
  label: "트렌드",
  background: "backgroundSubtle",
};

function selectCategoryThumbnail(categories: TrendCategoryItem[]): CategoryThumbnail {
  // The API has a deterministic display order, not a primary-category field.
  for (const { parent } of categories) {
    if (parent.category_code !== null) {
      const thumbnail = CATEGORY_THUMBNAILS.get(parent.category_code);
      if (thumbnail) {
        return thumbnail;
      }
    }
  }
  return DEFAULT_THUMBNAIL;
}

export interface TrendCardProps {
  displayNumber?: number;
  trend: TrendListItem;
  onOpenSource: (uri: string) => void;
}

function formatCollectedAt(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "최근 업데이트 시각을 확인할 수 없습니다.";
  }

  const formatted = new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);

  return `최근 업데이트 ${formatted}`;
}

export function TrendCard({
  displayNumber,
  trend,
  onOpenSource,
}: TrendCardProps) {
  const { styles, colors } = useStyles();
  const [failedThumbnailUrl, setFailedThumbnailUrl] = useState<string | null>(
    null,
  );

  const thumbnailUrl = trend.thumbnail_url;

  const shouldShowThumbnail =
    thumbnailUrl !== null && failedThumbnailUrl !== thumbnailUrl;
  const fallback = selectCategoryThumbnail(trend.categories);

  return (
    <View style={styles.card}>
      {displayNumber !== undefined && (
        <Text style={styles.displayNumber}>{`#${displayNumber}`}</Text>
      )}

      <View style={styles.mainContent}>
        <View style={styles.copy}>
          <Text numberOfLines={textLineLimits.itemTitle} style={styles.title}>
            {trend.title}
          </Text>

          {trend.summary !== null && (
            <Text numberOfLines={3} style={styles.summary}>
              {trend.summary}
            </Text>
          )}
        </View>

        {shouldShowThumbnail ? (
          <Image
            accessibilityLabel={`${trend.title} 썸네일`}
            onError={() => {
              setFailedThumbnailUrl(thumbnailUrl);
            }}
            resizeMode="cover"
            source={{
              uri: thumbnailUrl,
            }}
            style={styles.thumbnail}
          />
        ) : (
          <View
            accessible
            accessibilityLabel={`카테고리 썸네일: ${fallback.label}`}
            style={[
              styles.thumbnail,
              styles.thumbnailFallback,
              { backgroundColor: colors[fallback.background] },
            ]}
          >
            <Text style={styles.thumbnailIcon}>{fallback.icon}</Text>
            <Text
              numberOfLines={1}
              adjustsFontSizeToFit
              style={styles.thumbnailLabel}
            >
              {fallback.label}
            </Text>
          </View>
        )}
      </View>

      <TrendCategoryChips categories={trend.categories} />

      <Text style={styles.updatedAt}>
        {formatCollectedAt(trend.last_collected_at)}
      </Text>

      <TrendSourceSection
        onOpenSource={onOpenSource}
        source={trend.latest_source}
        topic={trend.title}
        relatedArticles={trend.related_articles}
      />
    </View>
  );
}

const useStyles = createThemedStyles((colors) => ({
  card: {
    gap: spacing.space3,
    padding: spacing.space4,
    borderWidth: borders.borderWidthDefault,
    borderColor: colors.borderDefault,
    borderRadius: radius.radiusMedium,
    backgroundColor: colors.backgroundSurface,
  },

  displayNumber: {
    ...typography.label,
    color: colors.textSecondary,
  },

  mainContent: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.space3,
  },

  copy: {
    flex: 1,
    gap: spacing.space2,
  },

  title: {
    ...typography.itemTitle,
    color: colors.textPrimary,
  },

  summary: {
    ...typography.body,
    color: colors.textSecondary,
  },

  thumbnail: {
    width: THUMBNAIL_SIZE,
    height: THUMBNAIL_SIZE,
    borderRadius: radius.radiusMedium,
    backgroundColor: colors.backgroundSubtle,
  },

  thumbnailFallback: {
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.space2,
    gap: spacing.space1,
  },

  thumbnailIcon: {
    ...typography.display,
    color: colors.textPrimary,
  },

  thumbnailLabel: {
    ...typography.label,
    color: colors.textPrimary,
    textAlign: "center",
  },

  updatedAt: {
    ...typography.caption,
    color: colors.textSecondary,
  },
}));
