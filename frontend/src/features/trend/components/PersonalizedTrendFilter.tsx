import { createThemedStyles } from "../../../shared/theme/createThemedStyles";
import { useEffect } from "react";
import { Text, View } from "react-native";

import { useCategories } from "../../interest/hooks/useCategories";
import { useUserInterests } from "../../interest/hooks/useUserInterests";
import { spacing, typography } from "../../../shared/constants";
import {
  TrendCategoryFilter,
  type TrendCategorySelection,
} from "./TrendCategoryFilter";

interface PersonalizedTrendFilterProps {
  selectedCategoryId: number | null;
  selectedRootCategoryId: number | null;
  onSelectionChange: (selection: TrendCategorySelection) => void;
}

/**
 * Only the user's selected root interests can appear in the personalized filter.
 * "All" stays on /trends/personalized; an explicit category selection uses
 * the existing /trends?category_id endpoint.
 */
export function PersonalizedTrendFilter({
  selectedCategoryId,
  selectedRootCategoryId,
  onSelectionChange,
}: PersonalizedTrendFilterProps) {
  const { styles } = useStyles();
  const categoriesQuery = useCategories();
  const interestsQuery = useUserInterests();

  const categories = categoriesQuery.data?.categories ?? [];
  const selectedRootIds = new Set(
    interestsQuery.data?.selected_category_ids ?? [],
  );
  const allowedRoots = categories.filter((category) =>
    selectedRootIds.has(category.category_id),
  );

  useEffect(() => {
    if (!categoriesQuery.data || !interestsQuery.data) return;
    if (selectedRootCategoryId === null) return;

    const currentRoot = allowedRoots.find(
      (category) => category.category_id === selectedRootCategoryId,
    );

    if (!currentRoot) {
      onSelectionChange({ rootCategoryId: null, categoryId: null });
    } else if (
      selectedCategoryId !== null &&
      selectedCategoryId !== currentRoot.category_id &&
      !currentRoot.children.some(
        (child) => child.category_id === selectedCategoryId,
      )
    ) {
      onSelectionChange({
        rootCategoryId: currentRoot.category_id,
        categoryId: currentRoot.category_id,
      });
    }
  }, [
    categoriesQuery.data,
    interestsQuery.data,
    selectedCategoryId,
    selectedRootCategoryId,
    onSelectionChange,
  ]);

  if (categoriesQuery.isPending || interestsQuery.isPending) {
    return null;
  }

  if (categoriesQuery.isError || interestsQuery.isError) {
    return (
      <Text style={styles.feedback}>
        관심사 필터를 불러오지 못했습니다.
      </Text>
    );
  }

  return (
    <View style={styles.filterRegion}>
      <TrendCategoryFilter
        categories={allowedRoots}
        selectedCategoryId={selectedCategoryId}
        selectedRootCategoryId={selectedRootCategoryId}
        onSelectionChange={onSelectionChange}
      />
    </View>
  );
}

const useStyles = createThemedStyles((colors) => ({
  filterRegion: {
    marginHorizontal: -spacing.screenGutter,
  },
  feedback: {
    ...typography.caption,
    color: colors.textSecondary,
  },
}));
