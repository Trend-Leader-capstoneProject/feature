import { useState } from "react";
import {
    ActivityIndicator,
    Alert,
    FlatList,
    Pressable,
    StyleSheet,
    Text,
    View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useCategories } from "../hooks/useCategories";
import type { CategoryItem } from "../types/category";

export function InterestSelectScreen() {
  const {
    data,
    isPending,
    isError,
    error,
    refetch,
  } = useCategories();

  const [selectedCategoryIds, setSelectedCategoryIds] =
    useState<number[]>([]);

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
  }: {
    item: CategoryItem;
  }) {
    const isSelected = selectedCategoryIds.includes(
      item.category_id,
    );

    return (
      <Pressable
        accessibilityRole="button"
        accessibilityState={{
          selected: isSelected,
        }}
        onPress={() => toggleCategory(item.category_id)}
        style={[
          styles.categoryCard,
          isSelected && styles.selectedCategoryCard,
        ]}
      >
        <Text
          style={[
            styles.categoryName,
            isSelected && styles.selectedCategoryName,
          ]}
        >
          {item.category_name}
        </Text>
      </Pressable>
    );
  }

  if (isPending) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <ActivityIndicator size="large" />
        <Text style={styles.stateMessage}>
          관심 분야를 불러오고 있습니다.
        </Text>
      </SafeAreaView>
    );
  }

  if (isError) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <Text style={styles.errorMessage}>
          {error.message}
        </Text>

        <Pressable
          onPress={() => void refetch()}
          style={styles.retryButton}
        >
          <Text style={styles.retryButtonText}>
            다시 시도
          </Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  const categories = data?.categories ?? [];

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>
          관심 분야를 선택해 주세요
        </Text>

        <Text style={styles.description}>
          선택한 관심 분야를 바탕으로 맞춤 트렌드를
          추천합니다.
        </Text>
      </View>

      <FlatList
        data={categories}
        keyExtractor={(item) =>
          item.category_id.toString()
        }
        renderItem={renderCategory}
        numColumns={2}
        columnWrapperStyle={styles.categoryRow}
        contentContainerStyle={styles.categoryList}
        ListEmptyComponent={
          <Text style={styles.stateMessage}>
            표시할 관심 분야가 없습니다.
          </Text>
        }
      />

      <Pressable
        disabled={selectedCategoryIds.length === 0}
        onPress={handleComplete}
        style={[
          styles.completeButton,
          selectedCategoryIds.length === 0 &&
            styles.disabledCompleteButton,
        ]}
      >
        <Text style={styles.completeButtonText}>
          선택 완료
        </Text>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 24,
    paddingBottom: 24,
    backgroundColor: "#FFFFFF",
  },
  centerContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
    paddingHorizontal: 24,
    backgroundColor: "#FFFFFF",
  },
  header: {
    paddingTop: 24,
    paddingBottom: 28,
  },
  title: {
    fontSize: 26,
    fontWeight: "700",
    color: "#111827",
  },
  description: {
    marginTop: 10,
    fontSize: 15,
    lineHeight: 22,
    color: "#6B7280",
  },
  categoryList: {
    flexGrow: 1,
    paddingBottom: 24,
  },
  categoryRow: {
    gap: 12,
    marginBottom: 12,
  },
  categoryCard: {
    flex: 1,
    minHeight: 112,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "#E5E7EB",
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
  },
  selectedCategoryCard: {
    borderColor: "#111827",
    backgroundColor: "#F3F4F6",
  },
  categoryName: {
    fontSize: 17,
    fontWeight: "600",
    color: "#374151",
  },
  selectedCategoryName: {
    color: "#111827",
  },
  stateMessage: {
    fontSize: 15,
    color: "#6B7280",
    textAlign: "center",
  },
  errorMessage: {
    fontSize: 15,
    color: "#B91C1C",
    textAlign: "center",
  },
  retryButton: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: "#111827",
  },
  retryButtonText: {
    color: "#FFFFFF",
    fontWeight: "600",
  },
  completeButton: {
    minHeight: 54,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 14,
    backgroundColor: "#111827",
  },
  disabledCompleteButton: {
    backgroundColor: "#D1D5DB",
  },
  completeButtonText: {
    fontSize: 17,
    fontWeight: "700",
    color: "#FFFFFF",
  },
});