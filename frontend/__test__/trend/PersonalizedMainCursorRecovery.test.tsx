import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react-native";
import { act, type ComponentProps } from "react";

import { useAuth } from "../../src/app/providers/AuthProvider";
import { MainPlaceholderScreen } from "../../src/app/screens/MainPlaceholderScreen";
import { getPersonalizedTrends } from "../../src/features/trend/api/getPersonalizedTrends";
import { trendQueryKeys } from "../../src/features/trend/queryKeys";
import type {
  TrendListData,
  TrendListItem,
} from "../../src/features/trend/types/trend";

jest.mock("../../src/app/providers/AuthProvider", () => ({
  useAuth: jest.fn(),
}));

jest.mock("../../src/features/trend/api/getPersonalizedTrends", () => ({
  getPersonalizedTrends: jest.fn(),
}));

const mockedUseAuth = jest.mocked(useAuth);
const mockedGetPersonalizedTrends = jest.mocked(getPersonalizedTrends);

type MainProps = ComponentProps<typeof MainPlaceholderScreen>;

const navigationMock = {
  navigate: jest.fn(),
} as unknown as MainProps["navigation"];

const routeMock = {
  key: "Main-cursor-recovery",
  name: "Main",
} as MainProps["route"];

function createTrend(trendId: number, title: string): TrendListItem {
  return {
    trend_id: trendId,
    title,
    summary: null,
    thumbnail_url: null,
    last_collected_at: "2026-10-01T09:00:00Z",
    categories: [],
    latest_source: null,
  };
}

describe("Personalized Main Cursor Recovery", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    mockedUseAuth.mockReturnValue({
      authState: {
        status: "AUTHENTICATED",
        session: {
          user: {
            user_id: 1,
            login_id: "trend_user",
            name: "테스트 사용자",
            status: "ACTIVE",
          },
          has_selected_interests: true,
          next_step: "MAIN",
        },
      },
      logout: jest.fn(async (): Promise<void> => undefined),
      revalidateSession: jest.fn(async (): Promise<void> => undefined),
    } as unknown as ReturnType<typeof useAuth>);
  });

  test("Main에서 INVALID_CURSOR 발생 시 Hook이 첫 페이지를 복구하고 새 목록을 표시한다", async () => {
    const oldPage: TrendListData = {
      items: [createTrend(101, "이전 관심사 트렌드")],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    const recoveredPage: TrendListData = {
      items: [createTrend(202, "복구된 관심사 트렌드")],
      next_cursor: null,
      has_next: false,
    };

    const invalidCursorError = Object.assign(
      new Error("유효하지 않은 Cursor입니다."),
      {
        isAxiosError: true,
        response: {
          status: 400,
          data: {
            success: false,
            statusCode: 400,
            message: "유효하지 않은 Cursor입니다.",
            data: {
              reason: "INVALID_CURSOR",
            },
          },
        },
      },
    );

    // 첫 페이지 성공 → 다음 페이지 오류 → 자동 복구 성공
    mockedGetPersonalizedTrends
      .mockResolvedValueOnce(oldPage)
      .mockRejectedValueOnce(invalidCursorError)
      .mockResolvedValueOnce(recoveredPage);

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: Infinity,
        },
      },
    });

    await render(
      <QueryClientProvider client={queryClient}>
        <MainPlaceholderScreen navigation={navigationMock} route={routeMock} />
      </QueryClientProvider>,
    );

    // 1. 최초 첫 페이지 표시
    await waitFor(() => {
      expect(screen.getByText("이전 관심사 트렌드")).toBeTruthy();
    });

    // 2. Main에서 추가 페이지 요청
    await fireEvent(
      screen.getByTestId("personalized-trend-list"),
      "endReached",
    );

    // 3. Hook이 INVALID_CURSOR를 복구하면
    //    Main에 새로운 첫 페이지가 표시된다.
    await waitFor(() => {
      expect(screen.getByText("복구된 관심사 트렌드")).toBeTruthy();
    });

    // 4. 이전 첫 페이지는 최종 목록에 남지 않는다.
    expect(screen.queryByText("이전 관심사 트렌드")).toBeNull();

    // 5. 복구 후 Footer 오류가 남지 않는다.
    expect(screen.queryByText("다음 트렌드를 불러오지 못했습니다.")).toBeNull();

    // 6. 요청 횟수: 최초 + 추가 페이지 + 자동 복구
    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(3);

    // 추가 페이지는 이전 Cursor 사용
    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      2,
      {
        cursor: "OLD_CURSOR",
        limit: 20,
      },
      expect.any(AbortSignal),
    );

    // 자동 복구는 Cursor 없는 첫 페이지부터
    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      3,
      {
        cursor: undefined,
        limit: 20,
      },
      expect.any(AbortSignal),
    );

    // 화면에서 별도 Navigation을 수행하지 않는다.
    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });

  test("Main에서 추가 페이지 요청 중 Refresh하면 늦은 이전 응답이 새 목록에 섞이지 않는다", async () => {
    const firstPage: TrendListData = {
      items: [createTrend(101, "새로고침 전 첫 페이지")],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    const oldSecondPage: TrendListData = {
      items: [createTrend(102, "취소된 이전 두 번째 페이지")],
      next_cursor: null,
      has_next: false,
    };

    const refreshedFirstPage: TrendListData = {
      items: [createTrend(202, "새로고침 후 첫 페이지")],
      next_cursor: null,
      has_next: false,
    };

    // 이전 추가 페이지 요청의 응답을 지연시킨다.
    let resolveOldSecondPage!: (value: TrendListData) => void;

    const oldSecondPagePromise = new Promise<TrendListData>((resolve) => {
      resolveOldSecondPage = resolve;
    });

    let oldPageSignal: AbortSignal | undefined;

    mockedGetPersonalizedTrends
      .mockResolvedValueOnce(firstPage)
      .mockImplementationOnce((_params, signal) => {
        oldPageSignal = signal;

        // 취소 신호를 무시하고 나중에 응답하는
        // 비동기 요청을 의도적으로 재현한다.
        return oldSecondPagePromise;
      })
      .mockResolvedValueOnce(refreshedFirstPage);

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          gcTime: Infinity,
        },
      },
    });

    await render(
      <QueryClientProvider client={queryClient}>
        <MainPlaceholderScreen navigation={navigationMock} route={routeMock} />
      </QueryClientProvider>,
    );

    // 1. 최초 첫 페이지가 표시된다.
    await waitFor(() => {
      expect(screen.getByText("새로고침 전 첫 페이지")).toBeTruthy();
    });

    // 2. OLD_CURSOR로 추가 페이지 요청을 시작한다.
    await fireEvent(
      screen.getByTestId("personalized-trend-list"),
      "endReached",
    );

    await waitFor(() => {
      expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(2);
    });

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      2,
      {
        cursor: "OLD_CURSOR",
        limit: 20,
      },
      expect.any(AbortSignal),
    );

    expect(oldPageSignal?.aborted).toBe(false);

    // 3. 추가 페이지가 응답하기 전에 Refresh를 실행한다.
    await fireEvent(screen.getByTestId("personalized-trend-list"), "refresh");

    // 4. Cursor 없는 첫 페이지 요청이 발생한다.
    await waitFor(() => {
      expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(3);
    });

    expect(mockedGetPersonalizedTrends).toHaveBeenNthCalledWith(
      3,
      {
        cursor: undefined,
        limit: 20,
      },
      expect.any(AbortSignal),
    );

    // 이전 추가 페이지 요청에는 취소 신호가 전달된다.
    expect(oldPageSignal?.aborted).toBe(true);

    // 5. 새로고침 결과가 Main에 반영된다.
    await waitFor(() => {
      expect(screen.getByText("새로고침 후 첫 페이지")).toBeTruthy();
    });

    expect(screen.queryByText("새로고침 전 첫 페이지")).toBeNull();

    // 6. 이전 추가 페이지의 응답을 뒤늦게 완료한다.
    await act(async () => {
      resolveOldSecondPage(oldSecondPage);
      await oldSecondPagePromise;
    });

    // 7. 늦은 응답이 새 목록에 합쳐지지 않아야 한다.
    expect(screen.getByText("새로고침 후 첫 페이지")).toBeTruthy();

    expect(screen.queryByText("취소된 이전 두 번째 페이지")).toBeNull();

    expect(screen.queryByText("새로고침 전 첫 페이지")).toBeNull();

    // 8. Query Cache도 새로운 첫 페이지 하나만 유지한다.
    expect(
      queryClient.getQueryData(trendQueryKeys.personalizedList(20)),
    ).toMatchObject({
      pages: [refreshedFirstPage],
      pageParams: [undefined],
    });

    // 9. API 요청은 정확히 3번만 발생한다.
    expect(mockedGetPersonalizedTrends).toHaveBeenCalledTimes(3);

    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });
});
