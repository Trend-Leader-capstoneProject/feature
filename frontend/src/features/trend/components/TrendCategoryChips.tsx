import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import {
  ScrollView,
  Text,
  View,
} from "react-native";

import { borders, radius, spacing, typography } from "../../../shared/constants";
import type {
  TrendCategoryItem,
} from "../types/trend";


export interface TrendCategoryChipsProps {
  categories: TrendCategoryItem[];
}

export function TrendCategoryChips({
  categories,
}: TrendCategoryChipsProps) {
  const { styles } = useStyles();
  if (categories.length === 0) {
    return null;
  }

  return (
    <ScrollView
      contentContainerStyle={
        styles.container
      }
      horizontal
      showsHorizontalScrollIndicator={
        false
      }
    >
      {categories.map(
        (category) => (
          <View
            key={category.category_id}
            style={styles.chip}
          >
            <Text
              numberOfLines={1}
              style={styles.label}
            >
              {`${category.parent.category_name} · ${category.category_name}`}
            </Text>
          </View>
        ),
      )}
    </ScrollView>
  );
}

const useStyles = createThemedStyles((colors) => ({
  container: {
    gap: spacing.space2,
  },

  chip: {
    paddingHorizontal:
      spacing.space3,
    paddingVertical:
      spacing.space2,
    borderWidth:
      borders.borderWidthDefault,
    borderColor:
      colors.borderDefault,
    borderRadius:
      radius.radiusFull,
    backgroundColor:
      colors.backgroundSubtle,
  },

  label: {
    ...typography.label,
    color:
      colors.textStrongSecondary,
  },
}));
