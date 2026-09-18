import {
    useEffect,
    useState,
} from "react";
import {
    FlatList,
    StyleSheet,
    Text,
    View,
    type ListRenderItemInfo,
} from "react-native";

import {
    EmptyView,
    ErrorView,
    LoadingView,
    PrimaryButton,
    ScreenContainer,
} from "../../../shared/components";
import {
    colors,
    spacing,
    textLineLimits,
    typography,
} from "../../../shared/constants";
import {
    InterestCategoryOption,
} from "../components";
import {
    useCategories,
} from "../hooks/useCategories";
import {
    useUserInterests,
} from "../hooks/useUserInterests";
import type {
    CategoryItem,
} from "../types/category";

function createInitialSelectedCategoryIds(
  categories: CategoryItem[],
  serverSelectedCategoryIds: number[],
): number[] {
  const selectableCategoryIds = new Set(
    categories.map(
      (category) => category.category_id,
    ),
  );

  return serverSelectedCategoryIds.filter(
    (categoryId) =>
      selectableCategoryIds.has(categoryId),
  );
}

function areSameCategoryIdSet(
  leftIds: number[],
  rightIds: number[],
): boolean {
  const leftSet = new Set(leftIds);
  const rightSet = new Set(rightIds);

  if (leftSet.size !== rightSet.size) {
    return false;
  }

  return [...leftSet].every(
    (categoryId) =>
      rightSet.has(categoryId),
  );
}

export function InterestEditScreen() {
  const {
    data: categoryData,
    isError: isCategoryError,
    isFetching: isCategoryFetching,
    isPending: isCategoryPending,
    refetch: refetchCategories,
  } = useCategories();

  const {
    data: interestData,
    isError: isInterestError,
    isFetching: isInterestFetching,
    isPending: isInterestPending,
    refetch: refetchUserInterests,
  } = useUserInterests();

  const [
    initialSelectedCategoryIds,
    setInitialSelectedCategoryIds,
  ] = useState<number[] | null>(null);

  const [
    selectedCategoryIds,
    setSelectedCategoryIds,
  ] = useState<number[]>([]);

  const categories =
    categoryData?.categories ?? [];

  const isDraftInitialized =
    initialSelectedCategoryIds !== null;

  const isDirty =
    initialSelectedCategoryIds !== null &&
    !areSameCategoryIdSet(
      selectedCategoryIds,
      initialSelectedCategoryIds,
    );

  const isSaveDisabled =
    !isDraftInitialized ||
    selectedCategoryIds.length === 0 ||
    !isDirty;

  useEffect(() => {
    if (
      initialSelectedCategoryIds !== null ||
      !categoryData ||
      !interestData
    ) {
      return;
    }

    const initialIds =
      createInitialSelectedCategoryIds(
        categoryData.categories,
        interestData.selected_category_ids,
      );

    setInitialSelectedCategoryIds(
      initialIds,
    );

    setSelectedCategoryIds(initialIds);
  }, [
    categoryData,
    interestData,
    initialSelectedCategoryIds,
  ]);

  function toggleCategory(
    categoryId: number,
  ): void {
    if (!isDraftInitialized) {
      return;
    }

    setSelectedCategoryIds(
      (currentIds) => {
        if (
          currentIds.includes(categoryId)
        ) {
          return currentIds.filter(
            (currentId) =>
              currentId !== categoryId,
          );
        }

        return [
          ...currentIds,
          categoryId,
        ];
      },
    );
  }

  function renderCategory({
    item,
  }: ListRenderItemInfo<CategoryItem>) {
    return (
      <InterestCategoryOption
        category={item}
        onPress={toggleCategory}
        selected={selectedCategoryIds.includes(
          item.category_id,
        )}
        style={styles.categoryOption}
      />
    );
  }

  function renderContent() {
    if (
      isCategoryPending ||
      isInterestPending
    ) {
      return (
        <LoadingView
          message="관심 분야를 불러오고 있습니다."
          style={styles.feedbackView}
        />
      );
    }

    if (
      isCategoryError &&
      categoryData === undefined
    ) {
      return (
        <ErrorView
          message="잠시 후 다시 시도해 주세요."
          onRetry={() =>
            void refetchCategories()
          }
          retrying={isCategoryFetching}
          style={styles.feedbackView}
          title="관심 분야 목록을 불러오지 못했습니다."
        />
      );
    }

    if (
      isInterestError &&
      interestData === undefined
    ) {
      return (
        <ErrorView
          message="잠시 후 다시 시도해 주세요."
          onRetry={() =>
            void refetchUserInterests()
          }
          retrying={isInterestFetching}
          style={styles.feedbackView}
          title="현재 관심 분야를 불러오지 못했습니다."
        />
      );
    }

    if (!isDraftInitialized) {
      return (
        <LoadingView
          message="현재 관심 분야를 준비하고 있습니다."
          style={styles.feedbackView}
        />
      );
    }

    return (
      <FlatList
        columnWrapperStyle={
          styles.categoryRow
        }
        contentContainerStyle={
          styles.categoryList
        }
        data={categories}
        extraData={
          selectedCategoryIds
        }
        keyExtractor={(item) =>
          item.category_id.toString()
        }
        ListEmptyComponent={
          <EmptyView
            style={styles.feedbackView}
            title="표시할 관심 분야가 없습니다."
          />
        }
        numColumns={2}
        renderItem={renderCategory}
        showsVerticalScrollIndicator={
          false
        }
      />
    );
  }

  return (
    <ScreenContainer>
      <View style={styles.header}>
        <Text
          accessibilityRole="header"
          numberOfLines={
            textLineLimits.screenTitle
          }
          style={styles.title}
        >
          관심 분야를 수정해 주세요
        </Text>

        <Text
          numberOfLines={3}
          style={styles.description}
        >
          관심 분야를 선택하거나 해제한 뒤 변경사항을 저장해 주세요.
        </Text>
      </View>

      <View style={styles.contentRegion}>
        {renderContent()}
      </View>

      <PrimaryButton
        disabled={isSaveDisabled}
        label="변경사항 저장"
        onPress={() => undefined}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  header: {
    gap: spacing.contentGap,
    marginBottom: spacing.sectionGap,
  },
  title: {
    ...typography.screenTitle,
    color: colors.textPrimary,
  },
  description: {
    ...typography.body,
    color: colors.textSecondary,
  },
  contentRegion: {
    flex: 1,
    marginBottom:
      spacing.bottomActionGap,
  },
  categoryList: {
    flexGrow: 1,
  },
  categoryRow: {
    gap: spacing.space3,
    marginBottom: spacing.space3,
  },
  categoryOption: {
    flex: 0.5,
  },
  feedbackView: {
    flex: 1,
  },
});
