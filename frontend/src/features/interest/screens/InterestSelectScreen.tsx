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
import { useSaveInterests } from "../hooks/useSaveInterests";
import type { CategoryItem } from "../types/category";

export function InterestSelectScreen() {
  const {
    data,
    isError: isCategoryError,
    isFetching: isCategoryFetching,
    isPending: isCategoryPending,
    refetch,
  } = useCategories();

  const saveInterestsMutation = useSaveInterests();

  const [selectedCategoryIds, setSelectedCategoryIds] =
    useState<number[]>([]);

  const categories = data?.categories ?? [];

  const hasSelectedCategories =
    selectedCategoryIds.length > 0;

  const isAlreadySaved =
    saveInterestsMutation.error?.response?.data.statusCode ===
    409;

  const isSelectionLocked =
    saveInterestsMutation.isPending ||
    saveInterestsMutation.isSuccess ||
    isAlreadySaved;

  const isSubmitDisabled =
    !hasSelectedCategories ||
    saveInterestsMutation.isPending ||
    saveInterestsMutation.isSuccess ||
    isAlreadySaved;

  function toggleCategory(categoryId: number): void {
    if (isSelectionLocked) {
      return;
    }

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
    if (isSubmitDisabled) {
      return;
    }

    saveInterestsMutation.mutate(
      {
        category_ids: selectedCategoryIds,
      },
      {
        onSuccess: (result) => {
          Alert.alert(
            "관심사 저장 완료",
            `${result.selected_count}개의 관심 분야를 저장했습니다.`,
          );
        },
        onError: (error) => {
          const errorResponse = error.response?.data;

          if (!errorResponse) {
            Alert.alert(
              "네트워크 오류",
              "서버에 연결할 수 없습니다. 네트워크 상태를 확인한 뒤 다시 시도해 주세요.",
            );
            return;
          }

          switch (errorResponse.statusCode) {
            case 400:
              setSelectedCategoryIds([]);
              void refetch();

              Alert.alert(
                "관심 분야를 다시 선택해 주세요",
                errorResponse.message,
              );
              return;

            case 401:
              Alert.alert(
                "로그인이 필요합니다",
                errorResponse.message,
              );
              return;

            case 404:
              setSelectedCategoryIds([]);
              void refetch();

              Alert.alert(
                "관심 분야 정보를 갱신합니다",
                errorResponse.message,
              );
              return;

            case 409:
              Alert.alert(
                "이미 저장된 관심사입니다",
                errorResponse.message,
              );
              return;

            case 422:
              Alert.alert(
                "선택 정보를 확인해 주세요",
                errorResponse.message,
              );
              return;

            case 500:
              Alert.alert(
                "관심사를 저장할 수 없습니다",
                errorResponse.message,
              );
              return;
          }
        },
      },
    );
  }

  function renderCategory({
    item,
  }: ListRenderItemInfo<CategoryItem>) {
    return (
      <InterestCategoryOption
        category={item}
        disabled={isSelectionLocked}
        onPress={toggleCategory}
        selected={selectedCategoryIds.includes(
          item.category_id,
        )}
        style={styles.categoryOption}
      />
    );
  }

  function renderContent() {
    if (isCategoryPending) {
      return (
        <LoadingView
          message="관심 분야를 불러오고 있습니다."
          style={styles.feedbackView}
        />
      );
    }

    if (isCategoryError && data === undefined) {
      return (
        <ErrorView
          message="잠시 후 다시 시도해 주세요."
          onRetry={() => void refetch()}
          retrying={isCategoryFetching}
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
        extraData={{
          selectedCategoryIds,
          isSelectionLocked,
        }}
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
        disabled={isSubmitDisabled}
        label={
          saveInterestsMutation.isSuccess
            ? "저장 완료"
            : isAlreadySaved
              ? "이미 저장됨"
              : "선택 완료"
        }
        loading={saveInterestsMutation.isPending}
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