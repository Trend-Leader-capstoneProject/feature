import { useState } from "react";
import {
  Alert,
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
import { InterestCategoryOption } from "../components";
import { useCategories } from "../hooks/useCategories";
import type { CategoryItem } from "../types/category";

export function InterestSelectScreen() {
  const {
    data,
    isError,
    isFetching,
    isPending,
    refetch,
  } = useCategories();

  const [selectedCategoryIds, setSelectedCategoryIds] =
    useState<number[]>([]);

  const categories = data?.categories ?? [];
  const hasSelectedCategories =
    selectedCategoryIds.length > 0;

  function toggleCategory(categoryId: number): void {
    setSelectedCategoryIds((currentIds) => {
      if (currentIds.includes(categoryId)) {
        return currentIds.filter(
          (currentId) => currentId !== categoryId,
        );
      }

      return [...currentIds, categoryId];
    });
  }

  function handleComplete(): void {
    Alert.alert(
      "선택 결과",
      `선택한 카테고리 ID: ${selectedCategoryIds.join(", ")}`,
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
    if (isPending) {
      return (
        <LoadingView
          message="관심 분야를 불러오고 있습니다."
          style={styles.feedbackView}
        />
      );
    }

    if (isError && data === undefined) {
      return (
        <ErrorView
          message="잠시 후 다시 시도해 주세요."
          onRetry={() => void refetch()}
          retrying={isFetching}
          style={styles.feedbackView}
          title="관심 분야를 불러오지 못했습니다."
        />
      );
    }

    return (
      <FlatList
        columnWrapperStyle={styles.categoryRow}
        contentContainerStyle={styles.categoryList}
        data={categories}
        extraData={selectedCategoryIds}
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
        showsVerticalScrollIndicator={false}
      />
    );
  }

  return (
    <ScreenContainer>
      <View style={styles.header}>
        <Text
          accessibilityRole="header"
          numberOfLines={textLineLimits.screenTitle}
          style={styles.title}
        >
          관심 분야를 선택해 주세요
        </Text>

        <Text
          numberOfLines={3}
          style={styles.description}
        >
          선택한 관심 분야를 바탕으로 맞춤 트렌드를 추천합니다.
        </Text>
      </View>

      <View style={styles.contentRegion}>
        {renderContent()}
      </View>

      <PrimaryButton
        disabled={!hasSelectedCategories}
        label="선택 완료"
        onPress={handleComplete}
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
    marginBottom: spacing.bottomActionGap,
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