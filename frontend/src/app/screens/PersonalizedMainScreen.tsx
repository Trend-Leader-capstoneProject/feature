import { useCallback, useEffect, useRef, useState } from "react";

import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
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

import {
  colors,
  radius,
  sizes,
  spacing,
  typography,
} from "../../shared/constants";

import type { AppStackParamList } from "../navigation/AppNavigator";

import { isAxiosError } from "axios";
import type { CommonErrorResponse } from "../../shared/types/api";
import { useAuth } from "../providers/AuthProvider";

type PersonalizedMainScreenProps = NativeStackScreenProps<
  AppStackParamList,
  "Main"
>;

export function PersonalizedMainScreen({
  navigation,
}: PersonalizedMainScreenProps) {
  const { authState, logout, revalidateSession } = useAuth();

  const {
    data: trendData,
    isPending,
    isError,
    isFetching,
    error,
    refetch,
    restart,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
    hasCursorRecoveryFailed,
  } = usePersonalizedTrends();

  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshInFlightRef = useRef(false);

  const [sessionRevalidationStatus, setSessionRevalidationStatus] = useState<
    "checking" | "failed" | "mismatch"
  >("checking");

  const handledNotInitializedErrorRef = useRef<unknown>(null);

  const nextPageRequestCursorRef = useRef<string | null>(null);

  // HTTP 상태와 machine-readable reason을 함께 확인한다.
  const isInterestsNotInitializedError =
    isError &&
    isAxiosError<CommonErrorResponse<TrendListErrorData, 409>>(error) &&
    error.response?.status === 409 &&
    error.response.data?.data?.reason === "INTERESTS_NOT_INITIALIZED";

  const isInterestsNotAvailableError =
    isError &&
    isAxiosError<CommonErrorResponse<TrendListErrorData, 409>>(error) &&
    error.response?.status === 409 &&
    error.response.data?.data?.reason === "INTERESTS_NOT_AVAILABLE";

  // 일반 홈 진입점은 초기 Loading 및 409 도메인 오류에서는 숨긴다.
  // INTERESTS_NOT_AVAILABLE은 기존 복구용 CTA를 사용한다.
  const showStandardInterestEditAction =
    !isPending &&
    !(isError && isAxiosError(error) && error.response?.status === 409);

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

  // 마지막 페이지에서 다음 요청에 사용할 Cursor를 확인한다.
  const lastPage = trendData?.pages[trendData.pages.length - 1];

  const nextCursor = lastPage?.next_cursor ?? null;

  const userName =
    authState.status === "AUTHENTICATED" ? authState.session.user.name : null;

  // 실제 맞춤 목록을 표시하는 상태에서만
  // 홈 헤더를 FlatList 내부에 배치한다.
  const isScrollableHome =
    trends.length > 0 &&
    !isInterestsNotInitializedError &&
    !isInterestsNotAvailableError &&
    !isPending &&
    !(isError && (trendData === undefined || hasCursorRecoveryFailed));
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

  function requestNextPage(): void {
    // 다음 페이지나 Cursor가 없으면 요청하지 않는다.
    if (!hasNextPage || nextCursor === null) {
      return;
    }

    // 이미 다음 페이지를 요청 중이면 중단한다.
    if (isFetchingNextPage) {
      return;
    }

    // 동일 Cursor의 진행 중인 요청을 중복 실행하지 않는다.
    if (nextPageRequestCursorRef.current === nextCursor) {
      return;
    }

    const requestCursor = nextCursor;

    // React의 다음 렌더링을 기다리지 않고 잠금을 설정한다.
    nextPageRequestCursorRef.current = requestCursor;

    void fetchNextPage()
      .catch(() => undefined)
      .finally(() => {
        if (nextPageRequestCursorRef.current === requestCursor) {
          nextPageRequestCursorRef.current = null;
        }
      });
  }

  function handleEndReached(): void {
    // 추가 페이지 오류 이후 스크롤 이벤트가 발생해도
    // 사용자의 명시적 요청 없이 자동 재시도하지 않는다.
    if (isFetchNextPageError) {
      return;
    }

    requestNextPage();
  }

  function handleRetryNextPage(): void {
    // 사용자가 직접 누른 Retry이므로
    // 이전 추가 페이지 오류 상태에서도 다시 요청할 수 있다.
    requestNextPage();
  }

  function handleRefresh(): void {
    // React의 상태 갱신을 기다리지 않고
    // 같은 시점의 중복 Refresh 요청을 차단한다.
    if (refreshInFlightRef.current) {
      return;
    }

    // 비동기 요청을 시작하기 전에 즉시 잠근다.
    refreshInFlightRef.current = true;

    // 사용자에게 Refresh 진행 상태를 표시한다.
    setIsRefreshing(true);

    // 기존 Pages와 Cursor를 폐기하고
    // 현재 관심사 기준 첫 페이지부터 재조회한다.
    void restart()
      .catch(() => undefined)
      .finally(() => {
        // 성공과 실패 모두 잠금을 해제한다.
        refreshInFlightRef.current = false;
        setIsRefreshing(false);
      });
  }

  function renderListFooter() {
    // 1. 추가 페이지 요청 중
    if (isFetchingNextPage) {
      return (
        <LoadingView accessibilityLabel="다음 트렌드를 불러오는 중입니다." />
      );
    }

    // 2. 추가 페이지 요청 실패
    if (isFetchNextPageError) {
      return (
        <ErrorView
          title="다음 트렌드를 불러오지 못했습니다."
          message="잠시 후 다시 시도해 주세요."
          retryLabel="다시 시도"
          onRetry={handleRetryNextPage}
          retrying={isFetchingNextPage}
        />
      );
    }

    // 3. 정상 상태에서는 Footer 표시하지 않음
    return null;
  }


function renderHomeHeader() {
  return (
    <>
      <View style={styles.header}>
        <View style={styles.topBar} testID="home-top-bar">
          <Text accessibilityRole="header" style={styles.title}>
            Trend Leader
          </Text>

          <Pressable
            accessibilityLabel="로그아웃"
            accessibilityRole="button"
            accessibilityState={{
              busy: isLoggingOut,
              disabled: isLoggingOut,
            }}
            disabled={isLoggingOut}
            onPress={() => {
              void handleLogout();
            }}
            style={({ pressed }) => [
              styles.logoutButton,
              pressed && !isLoggingOut && styles.secondaryPressed,
            ]}
          >
            {isLoggingOut && (
              <ActivityIndicator
                color={colors.textSecondary}
                size="small"
              />
            )}
            <Text style={styles.logoutButtonText}>
              로그아웃
            </Text>
          </Pressable>
        </View>

        <Text style={styles.description}>
          {userName
            ? `${userName}님, 관심 분야의 최신 흐름을 확인해 보세요.`
            : "관심 분야의 최신 흐름을 확인해 보세요."}
        </Text>
      </View>

      <View
        style={styles.personalizedSection}
        testID="home-personalized-section"
      >
        <View
          style={styles.actions}
          testID="home-quick-actions"
        >
          {showStandardInterestEditAction && (
            <View style={styles.sectionHeadingRow}>
              <Text
                accessibilityRole="header"
                style={styles.personalizedSectionTitle}
              >
                관심사 맞춤 트렌드
              </Text>

              <Pressable
                accessibilityLabel="관심사 수정하기"
                accessibilityRole="button"
                onPress={() => {
                  navigation.navigate("InterestEdit");
                }}
                style={({ pressed }) => [
                  styles.interestEditButton,
                  pressed && styles.secondaryPressed,
                ]}
              >
                <Text style={styles.interestEditText}>
                  관심사 수정
                </Text>
              </Pressable>
            </View>
          )}

          <View style={styles.latestActionRow}>
            <Pressable
              accessibilityLabel="최신 트렌드 보기"
              accessibilityRole="button"
              onPress={() => {
                navigation.navigate("LatestTrend");
              }}
              style={({ pressed }) => [
                styles.latestTrendButton,
                pressed && styles.secondaryPressed,
              ]}
            >
              <Text style={styles.latestTrendText}>
                전체 최신 보기 ↗
              </Text>
            </Pressable>
          </View>
        </View>
      </View>
    </>
  );
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

    // Phase 5-3B: 저장된 관심사의 유효 조회 범위가 없는 경우
    if (isInterestsNotAvailableError) {
      return (
        <View style={styles.interestsNotAvailable}>
          <ErrorView
            title="현재 관심사로 맞춤 트렌드를 조회할 수 없습니다."
            message="관심사 설정을 수정한 후 다시 확인해 주세요."
          />

          <PrimaryButton
            label="관심사 수정하기"
            onPress={() => {
              navigation.navigate("InterestEdit");
            }}
          />
        </View>
      );
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
    // Phase 5-2B: 정상 조회된 목록
    if (isScrollableHome) {
      return (
        <FlatList
          contentContainerStyle={styles.trendList}
          data={trends}
          keyExtractor={(item) => item.trend_id.toString()}
          ListHeaderComponent={renderHomeHeader()}
          ListFooterComponent={renderListFooter}
          onEndReached={handleEndReached}
          onEndReachedThreshold={0.4}
          onRefresh={handleRefresh}
          refreshing={isRefreshing}
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
      {!isScrollableHome && renderHomeHeader()}

      <View style={styles.contentRegion}>{renderContent()}</View>
    </ScreenContainer>
  );
}


const styles = StyleSheet.create({
  // 1. 홈 상단 헤더
  header: {
    gap: spacing.space2,
    marginBottom: spacing.space6,
  },

  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: spacing.space2,
  },

  title: {
    ...typography.screenTitle,
    color: colors.textPrimary,
    flexShrink: 1,
  },

  description: {
    ...typography.body,
    color: colors.textSecondary,
  },

  // 2. 개인화 트렌드 섹션
  personalizedSection: {
    marginBottom: spacing.space2,
  },

  actions: {
    gap: spacing.space2,
  },

  sectionHeadingRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: spacing.inlineGap,
  },

  personalizedSectionTitle: {
    ...typography.sectionTitle,
    color: colors.textPrimary,
    flexShrink: 1,
  },

  // 3. 관심사 수정 보조 버튼
  interestEditButton: {
    minHeight: sizes.touchTarget,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: spacing.space3,
    borderWidth: 1,
    borderColor: colors.borderDefault,
    borderRadius: radius.radiusMedium,
    backgroundColor: colors.backgroundSurface,
  },

  interestEditText: {
    ...typography.label,
    color: colors.textStrongSecondary,
  },

  // 4. 전체 최신 트렌드 이동 링크
  latestActionRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
  },

  latestTrendButton: {
    minHeight: sizes.touchTarget,
    justifyContent: "center",
    paddingHorizontal: spacing.space2,
    borderRadius: radius.radiusMedium,
  },

  latestTrendText: {
    ...typography.label,
    color: colors.textLink,
  },

  // 5. 로그아웃 보조 액션
  logoutButton: {
    minHeight: sizes.touchTarget,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.inlineGap,
    paddingHorizontal: spacing.space2,
    borderRadius: radius.radiusMedium,
    backgroundColor: "transparent",
  },

  logoutButtonText: {
    ...typography.label,
    color: colors.textSecondary,
  },

  secondaryPressed: {
    backgroundColor: colors.backgroundSubtle,
  },

  // 6. 기존 콘텐츠 및 목록 레이아웃 유지
  contentRegion: {
    flex: 1,
  },

  interestsNotAvailable: {
    gap: spacing.contentGap,
  },

  trendList: {
    gap: spacing.itemGap,
    paddingBottom: spacing.screenBottomSpacing,
  },
});
