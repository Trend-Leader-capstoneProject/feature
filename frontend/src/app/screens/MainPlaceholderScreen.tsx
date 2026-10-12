import { useCallback, useEffect, useRef, useState } from "react";

import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import {
  Alert,
  FlatList,
  StyleSheet,
  Text,
  View,
  type ListRenderItemInfo,
} from "react-native";

import { TrendCard } from "../../features/trend/components/TrendCard";
import { usePersonalizedTrends } from "../../features/trend/hooks/usePersonalizedTrends";
import type {
  TrendListErrorData,
  TrendListItem,
} from "../../features/trend/types/trend";
import { openTrendSourceUrl } from "../../features/trend/utils/openTrendSourceUrl";

import {
  EmptyView,
  ErrorView,
  LoadingView,
  PrimaryButton,
  ScreenContainer,
} from "../../shared/components";

import { colors, spacing, typography } from "../../shared/constants";

import type { AppStackParamList } from "../navigation/AppNavigator";

import { isAxiosError } from "axios";
import type { CommonErrorResponse } from "../../shared/types/api";
import { useAuth } from "../providers/AuthProvider";

type MainPlaceholderScreenProps = NativeStackScreenProps<
  AppStackParamList,
  "Main"
>;

export function MainPlaceholderScreen({
  navigation,
}: MainPlaceholderScreenProps) {
  const { authState, logout, revalidateSession } = useAuth();

  const {
    data: trendData,
    isPending,
    isError,
    isFetching,
    error,
    refetch,
    hasCursorRecoveryFailed,
  } = usePersonalizedTrends();

  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const [sessionRevalidationStatus, setSessionRevalidationStatus] = useState<
    "checking" | "failed" | "mismatch"
  >("checking");

  const handledNotInitializedErrorRef = useRef<unknown>(null);

  // HTTP 상태와 machine-readable reason을 함께 확인한다.
  const isInterestsNotInitializedError =
    isError &&
    isAxiosError<CommonErrorResponse<TrendListErrorData, 409>>(error) &&
    error.response?.status === 409 &&
    error.response.data?.data?.reason === "INTERESTS_NOT_INITIALIZED";

  const handleSessionRevalidation = useCallback((): void => {
    setSessionRevalidationStatus("checking");

    void revalidateSession()
      .then(() => {
        // Session 확인은 성공했다.
        // Onboarding 전환은 RootNavigator에 위임한다.
        // Main이 계속 유지되는 경우에는 불일치 UI를 제공한다.
        setSessionRevalidationStatus("mismatch");
      })
      .catch(() => {
        // Session 확인 요청 자체가 실패했다.
        setSessionRevalidationStatus("failed");
      });
  }, [revalidateSession]);

  useEffect(() => {
    if (!isInterestsNotInitializedError) {
      handledNotInitializedErrorRef.current = null;
      return;
    }

    // 동일한 오류 객체에 대해서는 자동 재검증하지 않는다.
    if (handledNotInitializedErrorRef.current === error) {
      return;
    }

    handledNotInitializedErrorRef.current = error;

    // 최초 감지 시 한 번만 자동 재검증한다.
    handleSessionRevalidation();
  }, [error, isInterestsNotInitializedError, handleSessionRevalidation]);

  // 여러 페이지의 Trend를 하나의 목록으로 변환한다.
  const trends = trendData?.pages.flatMap((page) => page.items) ?? [];

  const userName =
    authState.status === "AUTHENTICATED" ? authState.session.user.name : null;

  async function handleLogout(): Promise<void> {
    if (isLoggingOut) {
      return;
    }

    setIsLoggingOut(true);

    try {
      await logout();
    } catch {
      setIsLoggingOut(false);

      Alert.alert(
        "로그아웃 실패",
        "저장된 인증 정보를 삭제하지 못했습니다. 다시 시도해 주세요.",
      );
    }
  }

  function handleOpenSource(url: string): void {
    void openTrendSourceUrl(url);
  }

  function renderTrend({ item }: ListRenderItemInfo<TrendListItem>) {
    return <TrendCard onOpenSource={handleOpenSource} trend={item} />;
  }

  function renderContent() {
    // Phase 5-3A: 관심사 미초기화 시 Session 재검증 우선

    if (isInterestsNotInitializedError) {
      if (sessionRevalidationStatus === "failed") {
        return (
          <ErrorView
            title="관심사 설정 상태를 확인하지 못했습니다."
            message="잠시 후 다시 확인해 주세요."
            retryLabel="다시 확인"
            onRetry={handleSessionRevalidation}
          />
        );
      }

      if (sessionRevalidationStatus === "mismatch") {
        return (
          <ErrorView
            title="관심사 설정 상태가 일치하지 않습니다."
            message="관심사 설정 상태를 다시 확인해 주세요."
            retryLabel="다시 확인"
            onRetry={handleSessionRevalidation}
          />
        );
      }

      return <LoadingView message="관심사 설정 상태를 확인하고 있습니다." />;
    }

    // Phase 5-2A: 최초 Loading
    if (isPending) {
      return (
        <LoadingView message="관심사에 맞는 트렌드를 불러오고 있습니다." />
      );
    }

    // Phase 5-2D: 데이터가 없는 상태의 일반 조회 오류

    if (isError && (trendData === undefined || hasCursorRecoveryFailed)) {
      return (
        <ErrorView
          title="관심사에 맞는 트렌드를 불러오지 못했습니다."
          message="잠시 후 다시 시도해 주세요."
          onRetry={() => {
            void refetch();
          }}
          retrying={isFetching}
        />
      );
    }

    // Phase 5-2B: 정상 조회된 목록
    if (trends.length > 0) {
      return (
        <FlatList
          contentContainerStyle={styles.trendList}
          data={trends}
          keyExtractor={(item) => item.trend_id.toString()}
          renderItem={renderTrend}
          showsVerticalScrollIndicator={false}
          testID="personalized-trend-list"
        />
      );
    }

    // Phase 5-2C: 정상 조회 결과가 비어 있는 경우
    if (trendData !== undefined && trends.length === 0) {
      return <EmptyView title="관심사에 맞는 트렌드가 아직 없습니다." />;
    }

    return null;
  }

  return (
    <ScreenContainer>
      <View style={styles.header}>
        <Text accessibilityRole="header" style={styles.title}>
          Trend Leader
        </Text>

        <Text style={styles.description}>
          {userName
            ? `${userName}님, 로그인되어 있습니다.`
            : "로그인 세션이 정상적으로 복원되었습니다."}
          {"\n"}
          관심사에 맞는 트렌드를 확인해 보세요.
        </Text>
      </View>

      <View style={styles.actions}>
        <PrimaryButton
          label="최신 트렌드 보기"
          onPress={() => {
            navigation.navigate("LatestTrend");
          }}
        />

        <PrimaryButton
          label="로그아웃"
          loading={isLoggingOut}
          onPress={() => {
            void handleLogout();
          }}
        />
      </View>

      <View style={styles.contentRegion}>{renderContent()}</View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  header: {
    gap: spacing.contentGap,
    marginBottom: spacing.sectionGap,
  },

  actions: {
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
  },

  trendList: {
    gap: spacing.itemGap,
    paddingBottom: spacing.screenBottomSpacing,
  },
});
