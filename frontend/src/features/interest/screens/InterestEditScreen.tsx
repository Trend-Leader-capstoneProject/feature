import {
  useEffect,
  useState,
} from "react";

import {
  useNavigation,
} from "@react-navigation/native";

import {
  Alert,
  FlatList,
  StyleSheet,
  Text,
  View,
  type ListRenderItemInfo,
} from "react-native";

import { useAuth } from "../../../app/providers/AuthProvider";
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
import { useUpdateInterests } from "../hooks/useUpdateInterests";
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

  const navigation = useNavigation();

  const {
    revalidateSession,
  } = useAuth();

  const updateInterestsMutation =
    useUpdateInterests();

  const isSaveDisabled =
    !isDraftInitialized ||
    selectedCategoryIds.length === 0 ||
    !isDirty ||
    updateInterestsMutation.isPending;

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
    if (
      !isDraftInitialized ||
      updateInterestsMutation.isPending
    ) {
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

  function handleSave(): void {
    if (isSaveDisabled) {
      return;
    }

    updateInterestsMutation.mutate(
      {
        category_ids:
          selectedCategoryIds,
      },
      {
        onSuccess: (data) => {
          setInitialSelectedCategoryIds(
            data.selected_category_ids,
          );

          setSelectedCategoryIds(
            data.selected_category_ids,
          );

          navigation.goBack();
        },

        onError: (error) => {
          const errorResponse =
            error.response?.data;

          if (!errorResponse) {
            Alert.alert(
              "네트워크 오류",
              "서버에 연결할 수 없습니다. 네트워크 상태를 확인한 뒤 다시 시도해 주세요.",
            );
            return;
          }

          switch (
            errorResponse.statusCode
          ) {
            case 400:
            case 404:
              void refetchCategories();

              Alert.alert(
                "관심 분야 정보를 확인해 주세요",
                errorResponse.message,
              );
              return;

            case 401:
              return;

            case 409:
              if (
                errorResponse.data.reason ===
                "INTERESTS_NOT_INITIALIZED"
              ) {
                revalidateAfterConflict();
              }
              return;

            case 422:
              Alert.alert(
                "선택 정보를 확인해 주세요",
                errorResponse.message,
              );
              return;

            case 500:
              Alert.alert(
                "관심 분야를 저장할 수 없습니다",
                errorResponse.message,
              );
              return;
          }
        },
      },
    );
  }


  function revalidateAfterConflict(): void {
    void revalidateSession().catch(() => {
      Alert.alert(
        "로그인 상태 확인 실패",
        "서버의 현재 상태를 확인하지 못했습니다.",
        [
          {
            text: "취소",
            style: "cancel",
          },
          {
            text: "다시 시도",
            onPress:
              revalidateAfterConflict,
          },
        ],
      );
    });
  }

  function renderCategory({
    item,
  }: ListRenderItemInfo<CategoryItem>) {
    return (
      <InterestCategoryOption
        category={item}
        disabled={
          updateInterestsMutation.isPending
        }
        onPress={toggleCategory}
        selected={
          selectedCategoryIds.includes(
            item.category_id,
          )
        }
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
        loading={
          updateInterestsMutation.isPending
        }
        onPress={handleSave}
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
