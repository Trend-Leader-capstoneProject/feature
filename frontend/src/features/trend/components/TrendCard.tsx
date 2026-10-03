import {
  useState,
} from "react";
import {
  Image,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  borders,
  colors,
  radius,
  spacing,
  textLineLimits,
  typography,
} from "../../../shared/constants";
import type {
  TrendListItem,
} from "../types/trend";
import {
  TrendCategoryChips,
} from "./TrendCategoryChips";
import {
  TrendSourceSection,
} from "./TrendSourceSection";


const THUMBNAIL_SIZE = 96;

export interface TrendCardProps {
  displayNumber: number;
  trend: TrendListItem;
  onOpenSource: (uri: string) => void;
}

function formatCollectedAt(
  value: string,
): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "최근 업데이트 시각을 확인할 수 없습니다.";
  }

  const formatted =
    new Intl.DateTimeFormat(
      "ko-KR",
      {
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      },
    ).format(date);

  return `최근 업데이트 ${formatted}`;
}

export function TrendCard({
  displayNumber,
  trend,
  onOpenSource,
}: TrendCardProps) {
  const [
    failedThumbnailUrl,
    setFailedThumbnailUrl,
  ] = useState<string | null>(null);

  const thumbnailUrl =
    trend.thumbnail_url;

  const shouldShowThumbnail =
    thumbnailUrl !== null &&
    failedThumbnailUrl !== thumbnailUrl;

  return (
    <View style={styles.card}>
      <Text style={styles.displayNumber}>
        {`#${displayNumber}`}
      </Text>

      <View style={styles.mainContent}>
        <View style={styles.copy}>
          <Text
            numberOfLines={
              textLineLimits.itemTitle
            }
            style={styles.title}
          >
            {trend.title}
          </Text>

          {trend.summary !== null && (
            <Text
              numberOfLines={3}
              style={styles.summary}
            >
              {trend.summary}
            </Text>
          )}
        </View>

        {shouldShowThumbnail && (
          <Image
            accessibilityLabel={
              `${trend.title} 썸네일`
            }
            onError={() => {
              setFailedThumbnailUrl(
                thumbnailUrl,
              );
            }}
            resizeMode="cover"
            source={{
              uri: thumbnailUrl,
            }}
            style={styles.thumbnail}
          />
        )}
      </View>

      <TrendCategoryChips
        categories={trend.categories}
      />

      <Text style={styles.updatedAt}>
        {formatCollectedAt(
          trend.last_collected_at,
        )}
      </Text>

      <TrendSourceSection
        onOpenSource={onOpenSource}
        source={trend.latest_source}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: spacing.space3,
    padding: spacing.space4,
    borderWidth:
      borders.borderWidthDefault,
    borderColor:
      colors.borderDefault,
    borderRadius:
      radius.radiusMedium,
    backgroundColor:
      colors.backgroundSurface,
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
    borderRadius:
      radius.radiusMedium,
    backgroundColor:
      colors.backgroundSubtle,
  },

  updatedAt: {
    ...typography.caption,
    color: colors.textSecondary,
  },
});
