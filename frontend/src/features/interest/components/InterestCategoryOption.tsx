import {
  Image,
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
import { interestCategoryIcons } from "../constants/interestCategoryIcons";
import type { CategoryItem } from "../types/category";

const CATEGORY_ICON_SIZE = 56;


export type InterestCategoryOptionProps = {
  category: CategoryItem;
  disabled?: boolean;
  onPress: (categoryId: number) => void;
  selected: boolean;
  style?: StyleProp<ViewStyle>;
};

export function InterestCategoryOption({
  category,
  disabled = false,
  onPress,
  selected,
  style,
}: InterestCategoryOptionProps) {
  const accessibilityHint = disabled
    ? "현재는 관심 분야 선택을 변경할 수 없습니다."
    : selected
      ? "두 번 탭하여 관심 분야 선택을 해제합니다."
      : "두 번 탭하여 관심 분야로 선택합니다.";

  const iconSource = category.category_code
    ? interestCategoryIcons[category.category_code]
    : null;

  return (
    <Pressable
      accessibilityHint={accessibilityHint}
      accessibilityLabel={category.category_name}
      accessibilityRole="button"
      accessibilityState={{
        disabled,
        selected,
      }}
      disabled={disabled}
      onPress={() => onPress(category.category_id)}
      style={({ pressed }) => [
        styles.option,
        selected && styles.selectedOption,
        pressed &&
          !disabled &&
          !selected &&
          styles.pressedOption,
        pressed &&
          !disabled &&
          selected &&
          styles.pressedSelectedOption,
        disabled && styles.disabledOption,
        style,
      ]}
    >

      {iconSource && (
        <Image
          accessible={false}
          resizeMode="contain"
          source={iconSource}
          style={[
            styles.categoryIcon,
            selected &&
              styles.selectedCategoryIcon,
          ]}
        />
      )}

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
    disabledOption: {
    opacity: 0.6,
  },
  categoryIcon: {
    width: CATEGORY_ICON_SIZE,
    height: CATEGORY_ICON_SIZE,
    tintColor: colors.textStrongSecondary,
  },
  selectedCategoryIcon: {
    tintColor: colors.textBrand,
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
