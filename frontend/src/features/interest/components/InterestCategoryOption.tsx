import {
  Pressable,
  StyleSheet,
  Text,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import {
  borders,
  colors,
  radius,
  spacing,
  textLineLimits,
  typography,
} from "../../../shared/constants";
import type { CategoryItem } from "../types/category";

export type InterestCategoryOptionProps = {
  category: CategoryItem;
  onPress: (categoryId: number) => void;
  selected: boolean;
  style?: StyleProp<ViewStyle>;
};

export function InterestCategoryOption({
  category,
  onPress,
  selected,
  style,
}: InterestCategoryOptionProps) {
  const accessibilityHint = selected
    ? "두 번 탭하여 관심 분야 선택을 해제합니다."
    : "두 번 탭하여 관심 분야로 선택합니다.";

  return (
    <Pressable
      accessibilityHint={accessibilityHint}
      accessibilityLabel={category.category_name}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={() => onPress(category.category_id)}
      style={({ pressed }) => [
        styles.option,
        selected && styles.selectedOption,
        pressed &&
          !selected &&
          styles.pressedOption,
        pressed &&
          selected &&
          styles.pressedSelectedOption,
        style,
      ]}
    >
      <Text
        numberOfLines={textLineLimits.itemTitle}
        style={[
          styles.categoryName,
          selected && styles.selectedCategoryName,
        ]}
      >
        {category.category_name}
      </Text>

      {selected && (
        <Text
          numberOfLines={textLineLimits.label}
          style={styles.selectedLabel}
        >
          선택됨
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  option: {
    minHeight: 112,
    alignItems: "flex-start",
    justifyContent: "center",
    gap: spacing.inlineGap,
    padding: spacing.space4,
    borderWidth: borders.borderWidthDefault,
    borderColor: colors.borderDefault,
    borderRadius: radius.radiusMedium,
    backgroundColor: colors.backgroundSurface,
  },
  pressedOption: {
    backgroundColor: colors.backgroundSubtle,
  },
  selectedOption: {
    borderWidth: borders.borderWidthStrong,
    borderColor: colors.borderSelected,
    backgroundColor: colors.backgroundSelected,
  },
  pressedSelectedOption: {
    backgroundColor: colors.backgroundBrandMuted,
  },
  categoryName: {
    ...typography.itemTitle,
    color: colors.textPrimary,
  },
  selectedCategoryName: {
    color: colors.textBrand,
  },
  selectedLabel: {
    ...typography.label,
    color: colors.textBrand,
  },
});
