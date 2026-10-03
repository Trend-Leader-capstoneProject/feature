import {
    Pressable,
    ScrollView,
    StyleSheet,
    Text,
    View,
} from "react-native";

import {
    borders,
    colors,
    radius,
    sizes,
    spacing,
    typography,
} from "../../../shared/constants";
import type {
    CategoryItem,
} from "../../interest/types/category";


export interface TrendCategorySelection {
  rootCategoryId: number | null;
  categoryId: number | null;
}

export interface TrendCategoryFilterProps {
  categories: CategoryItem[];
  selectedCategoryId: number | null;
  selectedRootCategoryId: number | null;
  onSelectionChange: (
    selection: TrendCategorySelection,
  ) => void;
}

interface CategoryChipProps {
  label: string;
  selected: boolean;
  onPress: () => void;
}

function CategoryChip({
  label,
  selected,
  onPress,
}: CategoryChipProps) {
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{
        selected,
      }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        selected &&
          styles.selectedChip,
        pressed &&
          !selected &&
          styles.pressedChip,
        pressed &&
          selected &&
          styles.pressedSelectedChip,
      ]}
    >
      <Text
        numberOfLines={1}
        style={[
          styles.chipLabel,
          selected &&
            styles.selectedChipLabel,
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

export function TrendCategoryFilter({
  categories,
  selectedCategoryId,
  selectedRootCategoryId,
  onSelectionChange,
}: TrendCategoryFilterProps) {
  const selectedRootCategory =
    categories.find(
      (category) =>
        category.category_id ===
        selectedRootCategoryId,
    ) ?? null;

  function selectAll(): void {
    onSelectionChange({
      rootCategoryId: null,
      categoryId: null,
    });
  }

  function selectRoot(
    rootCategoryId: number,
  ): void {
    onSelectionChange({
      rootCategoryId,
      categoryId: rootCategoryId,
    });
  }

  function selectChild(
    childCategoryId: number,
  ): void {
    if (!selectedRootCategory) {
      return;
    }

    onSelectionChange({
      rootCategoryId:
        selectedRootCategory.category_id,
      categoryId: childCategoryId,
    });
  }

  return (
    <View
      accessibilityLabel="트렌드 카테고리 필터"
      style={styles.container}
    >
      <ScrollView
        contentContainerStyle={
          styles.chipRow
        }
        horizontal
        showsHorizontalScrollIndicator={
          false
        }
      >
        <CategoryChip
          label="전체"
          onPress={selectAll}
          selected={
            selectedRootCategoryId ===
              null &&
            selectedCategoryId === null
          }
        />

        {categories.map(
          (category) => (
            <CategoryChip
              key={
                category.category_id
              }
              label={
                category.category_name
              }
              onPress={() =>
                selectRoot(
                  category.category_id,
                )
              }
              selected={
                category.category_id ===
                selectedRootCategoryId
              }
            />
          ),
        )}
      </ScrollView>

      {selectedRootCategory && (
        <ScrollView
          contentContainerStyle={
            styles.chipRow
          }
          horizontal
          showsHorizontalScrollIndicator={
            false
          }
        >
          <CategoryChip
            label={
              `${selectedRootCategory.category_name} 전체`
            }
            onPress={() =>
              selectRoot(
                selectedRootCategory.category_id,
              )
            }
            selected={
              selectedCategoryId ===
              selectedRootCategory.category_id
            }
          />

          {selectedRootCategory.children.map(
            (child) => (
              <CategoryChip
                key={
                  child.category_id
                }
                label={
                  child.category_name
                }
                onPress={() =>
                  selectChild(
                    child.category_id,
                  )
                }
                selected={
                  selectedCategoryId ===
                  child.category_id
                }
              />
            ),
          )}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.space2,
  },

  chipRow: {
    gap: spacing.space2,
    paddingHorizontal:
      spacing.screenGutter,
  },

  chip: {
    minHeight:
      sizes.compactControlHeight,
    justifyContent: "center",
    paddingHorizontal:
      spacing.space4,
    borderWidth:
      borders.borderWidthDefault,
    borderColor:
      colors.borderDefault,
    borderRadius:
      radius.radiusFull,
    backgroundColor:
      colors.backgroundSurface,
  },

  selectedChip: {
    borderColor:
      colors.borderSelected,
    backgroundColor:
      colors.backgroundSelected,
  },

  pressedChip: {
    backgroundColor:
      colors.backgroundSubtle,
  },

  pressedSelectedChip: {
    backgroundColor:
      colors.backgroundBrandMuted,
  },

  chipLabel: {
    ...typography.label,
    color: colors.textPrimary,
  },

  selectedChipLabel: {
    color: colors.textBrand,
  },
});
