import {
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


export interface TrendCardProps {
  displayNumber: number;
  trend: TrendListItem;
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
}: TrendCardProps) {
  return (
    <View style={styles.card}>
      <Text style={styles.displayNumber}>
        {`#${displayNumber}`}
      </Text>

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

      <TrendCategoryChips
        categories={trend.categories}
      />

      <Text style={styles.updatedAt}>
        {formatCollectedAt(
          trend.last_collected_at,
        )}
      </Text>
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

  title: {
    ...typography.itemTitle,
    color: colors.textPrimary,
  },

  summary: {
    ...typography.body,
    color: colors.textSecondary,
  },

  updatedAt: {
    ...typography.caption,
    color: colors.textSecondary,
  },
});
