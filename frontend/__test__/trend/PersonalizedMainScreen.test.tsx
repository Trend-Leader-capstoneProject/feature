import { fireEvent, render, screen } from "@testing-library/react-native";
import type { ComponentProps } from "react";

import { useAuth } from "../../src/app/providers/AuthProvider";
import { MainPlaceholderScreen } from "../../src/app/screens/MainPlaceholderScreen";
import { usePersonalizedTrends } from "../../src/features/trend/hooks/usePersonalizedTrends";
import { TrendListData } from "../../src/features/trend/types/trend";

jest.mock("../../src/app/providers/AuthProvider", () => ({
  useAuth: jest.fn(),
}));

jest.mock("../../src/features/trend/hooks/usePersonalizedTrends", () => ({
  usePersonalizedTrends: jest.fn(),
}));

const mockedUseAuth = jest.mocked(useAuth);

const mockedUsePersonalizedTrends = jest.mocked(usePersonalizedTrends);

type MainScreenProps = ComponentProps<typeof MainPlaceholderScreen>;

const navigationMock = {
  navigate: jest.fn(),
} as unknown as MainScreenProps["navigation"];

const routeMock = {
  key: "Main-test",
  name: "Main",
} as MainScreenProps["route"];

describe("Personalized Main", () => {
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
    } as unknown as ReturnType<typeof useAuth>);
  });

  test("Main 최초 조회 중 맞춤 트렌드 Loading을 표시한다", async () => {
    mockedUsePersonalizedTrends.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      isFetching: true,
    } as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <MainPlaceholderScreen navigation={navigationMock} route={routeMock} />,
    );

    // Main 진입 시 맞춤 트렌드 Hook을 사용해야 한다.
    expect(mockedUsePersonalizedTrends).toHaveBeenCalledTimes(1);

    expect(
      screen.getByText("관심사에 맞는 트렌드를 불러오고 있습니다."),
    ).toBeTruthy();

    // 기존 전체 최신 트렌드 진입점은 유지한다.
    expect(
      screen.getByRole("button", {
        name: "최신 트렌드 보기",
      }),
    ).toBeTruthy();
  });

  test("Personalized Main은 여러 페이지의 TrendCard를 순번 없이 표시한다", async () => {
    const firstPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "AI 기술 트렌드",
          summary: "최근 AI 기술 관련 소식입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: "CURSOR_PAGE_2",
      has_next: true,
    };

    const secondPage: TrendListData = {
      items: [
        {
          trend_id: 102,
          title: "게임 산업 트렌드",
          summary: "최근 게임 산업 관련 소식입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T08:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: null,
      has_next: false,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [firstPage, secondPage],
        pageParams: [undefined, "CURSOR_PAGE_2"],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      hasNextPage: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
    } as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <MainPlaceholderScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 서로 다른 페이지의 Trend가 모두 표시된다.
    expect(screen.getByText("AI 기술 트렌드")).toBeTruthy();

    expect(screen.getByText("게임 산업 트렌드")).toBeTruthy();

    // 2. TrendCard의 Summary도 정상 표시한다.
    expect(screen.getByText("최근 AI 기술 관련 소식입니다.")).toBeTruthy();

    expect(screen.getByText("최근 게임 산업 관련 소식입니다.")).toBeTruthy();

    // 3. 맞춤 트렌드에는 순번을 표시하지 않는다.
    expect(screen.queryByText(/^#\d+$/)).toBeNull();

    // 4. 정상 조회 후 Loading 메시지가 사라진다.
    expect(
      screen.queryByText("관심사에 맞는 트렌드를 불러오고 있습니다."),
    ).toBeNull();

    // 5. 기존 전체 최신 트렌드 진입점 유지
    expect(
      screen.getByRole("button", {
        name: "최신 트렌드 보기",
      }),
    ).toBeTruthy();
  });

  test("정상 조회 결과가 비어 있으면 Personalized Empty 안내를 표시한다", async () => {
    const emptyPage: TrendListData = {
      items: [],
      next_cursor: null,
      has_next: false,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [emptyPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      hasNextPage: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
    } as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <MainPlaceholderScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 정상 Empty 안내 표시
    expect(
      screen.getByText("관심사에 맞는 트렌드가 아직 없습니다."),
    ).toBeTruthy();

    // 2. 트렌드 목록은 생성되지 않는다.
    expect(screen.queryByTestId("personalized-trend-list")).toBeNull();

    // 3. Loading 메시지는 표시되지 않는다.
    expect(
      screen.queryByText("관심사에 맞는 트렌드를 불러오고 있습니다."),
    ).toBeNull();

    // 4. 기존 전체 최신 트렌드 진입점 유지
    expect(
      screen.getByRole("button", {
        name: "최신 트렌드 보기",
      }),
    ).toBeTruthy();
  });

  test("최초 맞춤 트렌드 조회 실패 시 Error를 표시하고 다시 시도한다", async () => {
    const refetchMock = jest.fn();

    mockedUsePersonalizedTrends.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isFetching: false,
      error: new Error("Network Error"),
      refetch: refetchMock,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <MainPlaceholderScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 일반 오류 안내가 표시되어야 한다.
    expect(
      screen.getByText("관심사에 맞는 트렌드를 불러오지 못했습니다."),
    ).toBeTruthy();

    // 2. 일반 오류를 정상 Empty로 오인하지 않는다.
    expect(
      screen.queryByText("관심사에 맞는 트렌드가 아직 없습니다."),
    ).toBeNull();

    // 3. Loading 메시지를 표시하지 않는다.
    expect(
      screen.queryByText("관심사에 맞는 트렌드를 불러오고 있습니다."),
    ).toBeNull();

    // 4. Retry 버튼을 누르면 refetch를 호출한다.
    await fireEvent.press(
      screen.getByRole("button", {
        name: "다시 시도",
      }),
    );

    expect(refetchMock).toHaveBeenCalledTimes(1);

    // 5. 기존 전체 최신 트렌드 진입점은 유지한다.
    expect(
      screen.getByRole("button", {
        name: "최신 트렌드 보기",
      }),
    ).toBeTruthy();
  });

  test("일반 오류 재조회 중에는 Retry 버튼을 비활성화한다", async () => {
    const refetchMock = jest.fn();

    // 이전 조회에서 오류가 발생했고,
    // 사용자의 재조회 요청이 진행 중인 상태
    mockedUsePersonalizedTrends.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isFetching: true,
      error: new Error("Network Error"),
      refetch: refetchMock,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <MainPlaceholderScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 기존 오류 안내를 유지한다.
    expect(
      screen.getByText("관심사에 맞는 트렌드를 불러오지 못했습니다."),
    ).toBeTruthy();

    // 2. Retry 버튼이 비활성화되어야 한다.
    const retryButton = screen.getByRole("button", {
      name: "다시 시도",
    });

    expect(retryButton).toHaveProp(
      "accessibilityState",
      expect.objectContaining({
        disabled: true,
        busy: true,
      }),
    );

    // 3. 재조회 진행 중에는 추가 호출을 막는다.
    await fireEvent.press(retryButton);

    expect(refetchMock).not.toHaveBeenCalled();
  });
});
