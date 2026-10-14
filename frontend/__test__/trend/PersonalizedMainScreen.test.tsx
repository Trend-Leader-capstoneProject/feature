import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react-native";
import { act, type ComponentProps } from "react";

import { Alert } from "react-native";
import { useAuth } from "../../src/app/providers/AuthProvider";
import { PersonalizedMainScreen } from "../../src/app/screens/PersonalizedMainScreen";
import { usePersonalizedTrends } from "../../src/features/trend/hooks/usePersonalizedTrends";
import { TrendListData } from "../../src/features/trend/types/trend";
import { colors } from "../../src/shared/constants";

jest.mock("../../src/app/providers/AuthProvider", () => ({
  useAuth: jest.fn(),
}));

jest.mock("../../src/features/trend/hooks/usePersonalizedTrends", () => ({
  usePersonalizedTrends: jest.fn(),
}));

const mockedUseAuth = jest.mocked(useAuth);

const mockedUsePersonalizedTrends = jest.mocked(usePersonalizedTrends);

type MainScreenProps = ComponentProps<typeof PersonalizedMainScreen>;

const navigationMock = {
  navigate: jest.fn(),
} as unknown as MainScreenProps["navigation"];

const revalidateSessionMock = jest.fn(async (): Promise<void> => undefined);

const routeMock = {
  key: "Main-test",
  name: "Main",
} as MainScreenProps["route"];

describe("Personalized Main", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    revalidateSessionMock.mockReset();
    revalidateSessionMock.mockResolvedValue(undefined);

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
      revalidateSession: revalidateSessionMock,

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
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
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
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // Home-H3D: 로그인 안내 대신 개인화 홈 문구를 표시한다.
    expect(
      screen.getByText(
        "테스트 사용자님, 관심 분야의 최신 흐름을 확인해 보세요.",
      ),
    ).toBeTruthy();

    expect(screen.queryByText(/로그인되어 있습니다/)).toBeNull();

    expect(
      screen.queryByText(/로그인 세션이 정상적으로 복원되었습니다/),
    ).toBeNull();

    // Home-H3: 헤더와 주요 기능이 FlatList 내부에 존재한다.
    const list = screen.getByTestId("personalized-trend-list");

    expect(within(list).getByText("Trend Leader")).toBeTruthy();

    expect(
      within(list).getByRole("button", {
        name: "관심사 수정하기",
      }),
    ).toBeTruthy();

    expect(
      within(list).getByRole("button", {
        name: "최신 트렌드 보기",
      }),
    ).toBeTruthy();

    // Home-H3C: 개인화 트렌드 섹션 제목이 존재한다.
    expect(
      within(list).getByRole("header", {
        name: "관심사 맞춤 트렌드",
      }),
    ).toBeTruthy();

    // Home-H3E: 빠른 탐색과 로그아웃을 분리한다.
    const quickActions = within(list).getByTestId("home-quick-actions");

    expect(
      within(quickActions).getByRole("button", {
        name: "관심사 수정하기",
      }),
    ).toBeTruthy();

    expect(
      within(quickActions).getByRole("button", {
        name: "최신 트렌드 보기",
      }),
    ).toBeTruthy();

    // 로그아웃은 빠른 탐색 영역에 포함하지 않는다.
    expect(
      within(quickActions).queryByRole("button", {
        name: "로그아웃",
      }),
    ).toBeNull();

    // 로그아웃 기능 자체는 유지한다.
    expect(
      within(list).getByRole("button", {
        name: "로그아웃",
      }),
    ).toBeTruthy();

    // Home-H3F: 로그아웃은 보조 액션 스타일을 사용한다.
    const logoutButton = within(list).getByRole("button", {
      name: "로그아웃",
    });

    expect(logoutButton).toHaveStyle({
      backgroundColor: colors.actionSecondary,
    });

    expect(screen.getByText("로그아웃")).toHaveStyle({
      color: colors.actionSecondaryText,
    });

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

  test("정상 맞춤 트렌드 목록에서 관심사 수정 화면으로 이동할 수 있다", async () => {
    const firstPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "관심사 맞춤 테스트 트렌드",
          summary: "정상 상태에서 관심사 수정 진입을 확인합니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: null,
      has_next: false,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [firstPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      hasNextPage: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      hasCursorRecoveryFailed: false,
      error: null,
    } as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 기존 맞춤 트렌드 목록을 정상적으로 표시한다.
    expect(screen.getByText("관심사 맞춤 테스트 트렌드")).toBeTruthy();

    // 2. 정상 상태에도 관심사 수정 진입점이 존재한다.
    const interestEditButton = screen.getByRole("button", {
      name: "관심사 수정하기",
    });

    expect(interestEditButton).toBeTruthy();

    // 3. 관심사 수정 진입점은 한 개여야 한다.
    expect(
      screen.getAllByRole("button", {
        name: "관심사 수정하기",
      }),
    ).toHaveLength(1);

    // 4. 사용자가 누르면 기존 InterestEdit Route로 이동한다.
    await fireEvent.press(interestEditButton);

    expect(navigationMock.navigate).toHaveBeenCalledWith("InterestEdit");

    // 5. 기존 전체 최신 트렌드 진입점도 유지한다.
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
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
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
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
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
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
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

  test("기존 Cache가 있는 일반 재조회 실패에서는 트렌드 목록을 유지한다", async () => {
    const cachedPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "캐시된 AI 기술 트렌드",
          summary: "이전에 정상 조회한 트렌드입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: null,
      has_next: false,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [cachedPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: true,
      isRefetchError: true,
      isFetching: false,
      error: new Error("Network Error"),
      hasNextPage: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 기존 캐시 목록을 유지한다.
    expect(screen.getByText("캐시된 AI 기술 트렌드")).toBeTruthy();

    expect(screen.getByText("이전에 정상 조회한 트렌드입니다.")).toBeTruthy();

    // 2. 전체 화면 Error로 대체하지 않는다.
    expect(
      screen.queryByText("관심사에 맞는 트렌드를 불러오지 못했습니다."),
    ).toBeNull();

    // 3. 정상 Empty로 오인하지 않는다.
    expect(
      screen.queryByText("관심사에 맞는 트렌드가 아직 없습니다."),
    ).toBeNull();

    // 4. Personalized 목록이 유지된다.
    expect(screen.getByTestId("personalized-trend-list")).toBeTruthy();
  });

  test("INVALID_CURSOR 복구 실패 시 기존 Cache 대신 오류 UI를 표시한다", async () => {
    const cachedPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "이전 관심사 트렌드",
          summary: "Cursor 복구 전에 조회한 데이터입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    const refetchMock = jest.fn();

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [cachedPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: true,
      isRefetchError: true,
      isFetching: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      hasNextPage: true,
      hasCursorRecoveryFailed: true,
      error: new Error("Recovery request failed"),
      refetch: refetchMock,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 복구 실패 시 오류 안내를 표시한다.
    expect(
      screen.getByText("관심사에 맞는 트렌드를 불러오지 못했습니다."),
    ).toBeTruthy();

    // 2. 기존 Cache를 정상 목록처럼 보여주지 않는다.
    expect(screen.queryByText("이전 관심사 트렌드")).toBeNull();

    expect(screen.queryByTestId("personalized-trend-list")).toBeNull();

    // 3. Retry 경로를 제공한다.
    await fireEvent.press(
      screen.getByRole("button", {
        name: "다시 시도",
      }),
    );

    expect(refetchMock).toHaveBeenCalledTimes(1);

    // 4. 전체 최신 트렌드 진입점은 유지한다.
    expect(
      screen.getByRole("button", {
        name: "최신 트렌드 보기",
      }),
    ).toBeTruthy();
  });

  test("INTERESTS_NOT_INITIALIZED 발생 시 Session을 재검증하고 직접 이동하지 않는다", async () => {
    const notInitializedError = Object.assign(
      new Error("관심사 초기화가 필요합니다."),
      {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            success: false,
            statusCode: 409,
            message: "관심사 초기화가 필요합니다.",
            data: {
              reason: "INTERESTS_NOT_INITIALIZED",
            },
          },
        },
      },
    );

    mockedUsePersonalizedTrends.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isFetching: false,
      hasCursorRecoveryFailed: false,
      error: notInitializedError,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    const mainScreen = (
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />
    );

    const rendered = await render(mainScreen);

    // 1. 서버의 Session 상태를 재확인한다.
    await waitFor(() => {
      expect(revalidateSessionMock).toHaveBeenCalledTimes(1);
    });

    // 2. Main에서 Onboarding으로 직접 이동하지 않는다.
    expect(navigationMock.navigate).not.toHaveBeenCalled();

    // 3. 동일 오류 상태에서 다시 렌더링되어도
    //    Session 재검증을 반복하지 않는다.
    await rendered.rerender(mainScreen);

    expect(revalidateSessionMock).toHaveBeenCalledTimes(1);
  });

  test("INTERESTS_NOT_INITIALIZED 재검증 중에는 기존 Cache를 표시하지 않는다", async () => {
    const cachedPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "이전 관심사 트렌드",
          summary: "이전에 조회된 데이터입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: null,
      has_next: false,
    };

    const notInitializedError = Object.assign(
      new Error("관심사 초기화가 필요합니다."),
      {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            success: false,
            statusCode: 409,
            message: "관심사 초기화가 필요합니다.",
            data: {
              reason: "INTERESTS_NOT_INITIALIZED",
            },
          },
        },
      },
    );

    // Session 재검증이 진행 중인 상태로 유지한다.
    revalidateSessionMock.mockImplementationOnce(
      () => new Promise<void>(() => undefined),
    );

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [cachedPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: true,
      isFetching: false,
      hasCursorRecoveryFailed: false,
      error: notInitializedError,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    await waitFor(() => {
      expect(revalidateSessionMock).toHaveBeenCalledTimes(1);
    });

    // 세션 확인 중이라는 안내를 표시한다.
    expect(
      screen.getByText("관심사 설정 상태를 확인하고 있습니다."),
    ).toBeTruthy();

    // 이전 Cache를 정상 목록처럼 표시하지 않는다.
    expect(screen.queryByText("이전 관심사 트렌드")).toBeNull();

    expect(screen.queryByTestId("personalized-trend-list")).toBeNull();

    // 409 오류를 일반 API Retry로 반복하지 않는다.
    expect(
      screen.queryByRole("button", {
        name: "다시 시도",
      }),
    ).toBeNull();

    // 직접 Onboarding으로 이동하지 않는다.
    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });

  test("INTERESTS_NOT_INITIALIZED 재검증 실패 시 Loading을 종료하고 복구 UI를 표시한다", async () => {
    const notInitializedError = Object.assign(
      new Error("관심사 초기화가 필요합니다."),
      {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            success: false,
            statusCode: 409,
            message: "관심사 초기화가 필요합니다.",
            data: {
              reason: "INTERESTS_NOT_INITIALIZED",
            },
          },
        },
      },
    );

    // Session 재검증이 실패하도록 설정한다.
    revalidateSessionMock.mockRejectedValueOnce(
      new Error("Session revalidation failed"),
    );

    // 현재 구현의 Alert를 테스트 환경에서 가로챈다.
    const alertSpy = jest
      .spyOn(Alert, "alert")
      .mockImplementation(() => undefined);

    mockedUsePersonalizedTrends.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isFetching: false,
      hasCursorRecoveryFailed: false,
      error: notInitializedError,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    try {
      await render(
        <PersonalizedMainScreen
          navigation={navigationMock}
          route={routeMock}
        />,
      );

      // 1. Session 재검증이 실행된다.
      await waitFor(() => {
        expect(revalidateSessionMock).toHaveBeenCalledTimes(1);
      });

      // 2. 재검증 실패 시 오류 안내를 표시한다.
      await waitFor(() => {
        expect(
          screen.getByText("관심사 설정 상태를 확인하지 못했습니다."),
        ).toBeTruthy();
      });

      // 3. 더 이상 Loading 화면에 머물지 않는다.
      expect(
        screen.queryByText("관심사 설정 상태를 확인하고 있습니다."),
      ).toBeNull();

      // 4. 사용자가 수동으로 재검증할 수 있다.
      expect(
        screen.getByRole("button", {
          name: "다시 확인",
        }),
      ).toBeTruthy();

      // 5. 직접 Navigation하지 않는다.
      expect(navigationMock.navigate).not.toHaveBeenCalled();
    } finally {
      alertSpy.mockRestore();
    }
  });

  test("INTERESTS_NOT_INITIALIZED 재검증 실패 후 수동 재시도를 실행한다", async () => {
    const notInitializedError = Object.assign(
      new Error("관심사 초기화가 필요합니다."),
      {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            success: false,
            statusCode: 409,
            message: "관심사 초기화가 필요합니다.",
            data: {
              reason: "INTERESTS_NOT_INITIALIZED",
            },
          },
        },
      },
    );

    // 첫 번째 자동 재검증은 실패한다.
    // 두 번째 수동 재검증은 성공하도록 설정한다.
    revalidateSessionMock
      .mockRejectedValueOnce(new Error("Session revalidation failed"))
      .mockResolvedValueOnce(undefined);

    mockedUsePersonalizedTrends.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isFetching: false,
      hasCursorRecoveryFailed: false,
      error: notInitializedError,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 최초 자동 재검증 실패
    await waitFor(() => {
      expect(
        screen.getByRole("button", {
          name: "다시 확인",
        }),
      ).toBeTruthy();
    });

    expect(revalidateSessionMock).toHaveBeenCalledTimes(1);

    // 2. 사용자가 다시 확인 버튼을 누른다.
    await fireEvent.press(
      screen.getByRole("button", {
        name: "다시 확인",
      }),
    );

    // 3. 수동 재검증을 정확히 한 번 실행한다.
    await waitFor(() => {
      expect(revalidateSessionMock).toHaveBeenCalledTimes(2);
    });

    // 4. 재검증을 시작하면 기존 오류 UI를 해제한다.
    expect(
      screen.queryByText("관심사 설정 상태를 확인하지 못했습니다."),
    ).toBeNull();

    // 5. Main에서 직접 Navigation하지 않는다.
    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });

  test("INTERESTS_NOT_INITIALIZED 재검증 성공 후 MAIN 유지 시 불일치 안내를 표시한다", async () => {
    const notInitializedError = Object.assign(
      new Error("관심사 초기화가 필요합니다."),
      {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            success: false,
            statusCode: 409,
            message: "관심사 초기화가 필요합니다.",
            data: {
              reason: "INTERESTS_NOT_INITIALIZED",
            },
          },
        },
      },
    );

    // 세션 재검증 요청은 성공하지만,
    // 테스트의 AuthState는 여전히 MAIN을 유지한다.
    revalidateSessionMock.mockResolvedValueOnce(undefined);

    mockedUsePersonalizedTrends.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isFetching: false,
      hasCursorRecoveryFailed: false,
      error: notInitializedError,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. Session을 정확히 한 번 재검증한다.
    await waitFor(() => {
      expect(revalidateSessionMock).toHaveBeenCalledTimes(1);
    });

    // 2. MAIN 상태가 유지되면 불일치 안내를 표시한다.
    await waitFor(() => {
      expect(
        screen.getByText("관심사 설정 상태가 일치하지 않습니다."),
      ).toBeTruthy();
    });

    // 3. 무한 Loading에 머무르지 않는다.
    expect(
      screen.queryByText("관심사 설정 상태를 확인하고 있습니다."),
    ).toBeNull();

    // 4. 사용자가 다시 확인할 수 있다.
    expect(
      screen.getByRole("button", {
        name: "다시 확인",
      }),
    ).toBeTruthy();

    // 5. 자동 재검증 반복 및 직접 Navigation 방지
    expect(revalidateSessionMock).toHaveBeenCalledTimes(1);

    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });

  test("INTERESTS_NOT_AVAILABLE 발생 시 Cache 대신 관심사 수정 안내와 이동 경로를 제공한다", async () => {
    const cachedPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "이전 관심사 트렌드",
          summary: "이전에 조회된 데이터입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: null,
      has_next: false,
    };

    const notAvailableError = Object.assign(
      new Error("현재 관심사로 조회할 수 없습니다."),
      {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            success: false,
            statusCode: 409,
            message: "현재 관심사로 조회할 수 없습니다.",
            data: {
              reason: "INTERESTS_NOT_AVAILABLE",
            },
          },
        },
      },
    );

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [cachedPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: true,
      isFetching: false,
      hasCursorRecoveryFailed: false,
      error: notAvailableError,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 관심사 수정 안내를 표시한다.
    expect(
      screen.getByText("현재 관심사로 맞춤 트렌드를 조회할 수 없습니다."),
    ).toBeTruthy();

    // 2. 이전 Cache를 정상 목록처럼 보여주지 않는다.
    expect(screen.queryByText("이전 관심사 트렌드")).toBeNull();

    expect(screen.queryByTestId("personalized-trend-list")).toBeNull();

    // 3. 관심사 수정 CTA가 있어야 한다.
    const editButton = screen.getByRole("button", {
      name: "관심사 수정하기",
    });

    expect(editButton).toBeTruthy();

    // 정상 상태 CTA와 복구용 CTA가 중복 표시되지 않는다.
    expect(
      screen.getAllByRole("button", {
        name: "관심사 수정하기",
      }),
    ).toHaveLength(1);

    // 4. 전체 최신 목록 진입점도 유지한다.
    expect(
      screen.getByRole("button", {
        name: "최신 트렌드 보기",
      }),
    ).toBeTruthy();

    // 5. Session 재검증을 실행하지 않는다.
    expect(revalidateSessionMock).not.toHaveBeenCalled();

    // 6. 사용자가 관심사 수정 화면으로 이동한다.
    await fireEvent.press(editButton);

    expect(navigationMock.navigate).toHaveBeenCalledWith("InterestEdit");

    expect(navigationMock.navigate).toHaveBeenCalledTimes(1);
  });

  test("다른 409 reason은 INTERESTS_NOT_AVAILABLE로 처리하지 않는다", async () => {
    const refetchMock = jest.fn();

    const otherConflictError = Object.assign(
      new Error("다른 종류의 Conflict가 발생했습니다."),
      {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            success: false,
            statusCode: 409,
            message: "다른 종류의 Conflict가 발생했습니다.",
            data: {
              reason: "CATEGORY_NOT_AVAILABLE",
            },
          },
        },
      },
    );

    mockedUsePersonalizedTrends.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      isFetching: false,
      hasCursorRecoveryFailed: false,
      error: otherConflictError,
      refetch: refetchMock,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 관심사 조회 불가로 잘못 분류하지 않는다.
    expect(
      screen.queryByText("현재 관심사로 맞춤 트렌드를 조회할 수 없습니다."),
    ).toBeNull();

    expect(
      screen.queryByRole("button", {
        name: "관심사 수정하기",
      }),
    ).toBeNull();

    // 관심사 미초기화로도 잘못 분류하지 않는다.
    expect(revalidateSessionMock).not.toHaveBeenCalled();

    // 알려지지 않은 Conflict는 일반 오류 UI로 처리한다.
    expect(
      screen.getByText("관심사에 맞는 트렌드를 불러오지 못했습니다."),
    ).toBeTruthy();

    // 사용자의 명시적인 재시도 경로를 제공한다.
    expect(
      screen.getByRole("button", {
        name: "다시 시도",
      }),
    ).toBeTruthy();

    // 자동 조회 반복이나 직접 Navigation은 발생하지 않는다.
    expect(refetchMock).not.toHaveBeenCalled();

    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });

  test("Personalized 목록 끝에 도달하면 다음 페이지를 요청한다", async () => {
    const fetchNextPageMock = jest.fn(async (): Promise<void> => undefined);

    const firstPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "첫 번째 맞춤 트렌드",
          summary: "첫 페이지 데이터입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: "NEXT_CURSOR",
      has_next: true,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [firstPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      hasNextPage: true,
      hasCursorRecoveryFailed: false,
      error: null,
      fetchNextPage: fetchNextPageMock,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 첫 페이지 데이터 표시
    expect(screen.getByText("첫 번째 맞춤 트렌드")).toBeTruthy();

    const list = screen.getByTestId("personalized-trend-list");

    // 2. 사용자가 목록 끝에 도달한다.
    await fireEvent(list, "endReached");

    // 3. 다음 페이지 요청이 실행된다.
    expect(fetchNextPageMock).toHaveBeenCalledTimes(1);

    // 4. 기존 Main Navigation은 변경되지 않는다.
    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });

  test("동일 Cursor의 endReached가 연속 발생해도 다음 페이지를 한 번만 요청한다", async () => {
    // 다음 페이지 요청의 완료 시점을 직접 제어한다.
    let resolveRequest!: () => void;

    const pendingRequest = new Promise<void>((resolve) => {
      resolveRequest = resolve;
    });

    const fetchNextPageMock = jest.fn(() => pendingRequest);

    const firstPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "첫 번째 맞춤 트렌드",
          summary: "첫 페이지 데이터입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: "NEXT_CURSOR",
      has_next: true,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [firstPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      hasNextPage: true,
      hasCursorRecoveryFailed: false,
      error: null,
      fetchNextPage: fetchNextPageMock,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    const list = screen.getByTestId("personalized-trend-list");

    // 1. 첫 번째 스크롤 끝 이벤트
    await fireEvent(list, "endReached");

    // 2. 첫 번째 요청이 완료되기 전에
    //    동일 이벤트가 다시 발생한다.
    await fireEvent(list, "endReached");

    // 3. 동일 Cursor에 대한 중복 요청을 방지한다.
    expect(fetchNextPageMock).toHaveBeenCalledTimes(1);

    // 4. 대기 중인 요청을 완료한다.
    await act(async () => {
      resolveRequest();
      await pendingRequest;
    });
  });

  test.each([
    {
      caseName: "다음 페이지가 없는 경우",
      hasNextPage: false,
      nextCursor: null,
    },
    {
      caseName: "다음 Cursor가 없는 경우",
      hasNextPage: true,
      nextCursor: null,
    },
  ])(
    "$caseName endReached에서 추가 요청하지 않는다",
    async ({ hasNextPage, nextCursor }) => {
      const fetchNextPageMock = jest.fn(async (): Promise<void> => undefined);

      const firstPage: TrendListData = {
        items: [
          {
            trend_id: 101,
            title: "마지막 맞춤 트렌드",
            summary: null,
            thumbnail_url: null,
            last_collected_at: "2026-10-01T09:00:00Z",
            categories: [],
            latest_source: null,
          },
        ],
        next_cursor: nextCursor,
        has_next: hasNextPage,
      };

      mockedUsePersonalizedTrends.mockReturnValue({
        data: {
          pages: [firstPage],
          pageParams: [undefined],
        },
        isPending: false,
        isError: false,
        isFetching: false,
        isFetchingNextPage: false,
        isFetchNextPageError: false,
        hasNextPage,
        hasCursorRecoveryFailed: false,
        error: null,
        fetchNextPage: fetchNextPageMock,
      } as unknown as ReturnType<typeof usePersonalizedTrends>);

      await render(
        <PersonalizedMainScreen
          navigation={navigationMock}
          route={routeMock}
        />,
      );

      // 기존 데이터는 정상 표시된다.
      expect(screen.getByText("마지막 맞춤 트렌드")).toBeTruthy();

      const list = screen.getByTestId("personalized-trend-list");

      // 목록 끝 이벤트가 반복 발생해도
      // 불필요한 요청을 생성해서는 안 된다.
      await fireEvent(list, "endReached");
      await fireEvent(list, "endReached");

      expect(fetchNextPageMock).not.toHaveBeenCalled();

      expect(navigationMock.navigate).not.toHaveBeenCalled();
    },
  );

  test("다음 페이지 조회 중 기존 TrendCard와 Footer Loading을 함께 표시한다", async () => {
    const firstPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "기존 맞춤 트렌드",
          summary: "첫 페이지 데이터입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: "NEXT_CURSOR",
      has_next: true,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [firstPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: false,
      isFetching: true,
      isFetchingNextPage: true,
      isFetchNextPageError: false,
      hasNextPage: true,
      hasCursorRecoveryFailed: false,
      error: null,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 기존 목록은 계속 표시된다.
    expect(screen.getByText("기존 맞춤 트렌드")).toBeTruthy();

    expect(screen.getByTestId("personalized-trend-list")).toBeTruthy();

    // 2. 목록 하단에 다음 페이지 Loading을 표시한다.
    expect(
      screen.getByLabelText("다음 트렌드를 불러오는 중입니다."),
    ).toBeTruthy();

    // 3. 최초 진입 Loading으로 되돌아가지 않는다.
    expect(
      screen.queryByText("관심사에 맞는 트렌드를 불러오고 있습니다."),
    ).toBeNull();

    // 4. 기존 Navigation은 변경되지 않는다.
    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });

  test("추가 페이지 조회 실패 시 기존 목록을 유지하고 Footer에서 수동 재시도한다", async () => {
    const fetchNextPageMock = jest.fn(async (): Promise<void> => undefined);

    const firstPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "기존 맞춤 트렌드",
          summary: "첫 페이지 데이터입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: "NEXT_CURSOR",
      has_next: true,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [firstPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: true,
      isFetching: false,
      isFetchingNextPage: false,
      isFetchNextPageError: true,
      hasNextPage: true,
      hasCursorRecoveryFailed: false,
      error: new Error("추가 페이지 조회 실패"),
      fetchNextPage: fetchNextPageMock,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 첫 페이지 목록은 유지한다.
    expect(screen.getByText("기존 맞춤 트렌드")).toBeTruthy();

    const list = screen.getByTestId("personalized-trend-list");

    // 2. 스크롤 끝 이벤트가 다시 발생해도
    //    자동으로 추가 페이지를 재요청하지 않는다.
    await fireEvent(list, "endReached");

    expect(fetchNextPageMock).not.toHaveBeenCalled();

    // 3. 전체 화면 오류 대신 Footer 오류를 표시한다.
    expect(screen.getByText("다음 트렌드를 불러오지 못했습니다.")).toBeTruthy();

    expect(
      screen.queryByText("관심사에 맞는 트렌드를 불러오지 못했습니다."),
    ).toBeNull();

    // 4. 사용자에게 수동 Retry를 제공한다.
    const retryButton = screen.getByRole("button", {
      name: "다시 시도",
    });

    await fireEvent.press(retryButton);

    expect(fetchNextPageMock).toHaveBeenCalledTimes(1);

    // 5. 화면 이동은 발생하지 않는다.
    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });

  test("Personalized Pull-to-refresh 시 refetch 대신 restart를 호출한다", async () => {
    const restartMock = jest.fn(async (): Promise<void> => undefined);

    const refetchMock = jest.fn(async (): Promise<void> => undefined);

    const firstPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "새로고침 전 맞춤 트렌드",
          summary: "기존 관심사 조회 결과입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: "OLD_CURSOR",
      has_next: true,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [firstPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      hasNextPage: true,
      hasCursorRecoveryFailed: false,
      error: null,
      refetch: refetchMock,
      restart: restartMock,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 기존 목록이 표시된다.
    expect(screen.getByText("새로고침 전 맞춤 트렌드")).toBeTruthy();

    const list = screen.getByTestId("personalized-trend-list");

    // 2. 사용자가 목록을 아래로 당겨 새로고침한다.
    await fireEvent(list, "refresh");

    // 3. Cursor Chain을 폐기하는 restart를 호출한다.
    expect(restartMock).toHaveBeenCalledTimes(1);

    // 4. 일반 refetch를 사용하면 안 된다.
    expect(refetchMock).not.toHaveBeenCalled();

    // 5. 직접 Navigation하지 않는다.
    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });

  test("Pull-to-refresh 중 기존 TrendCard를 유지하고 Refresh 상태를 표시한다", async () => {
    // restart()의 완료 시점을 테스트에서 직접 제어한다.
    let resolveRestart!: () => void;

    const pendingRestart = new Promise<void>((resolve) => {
      resolveRestart = resolve;
    });

    const restartMock = jest.fn(() => pendingRestart);

    const firstPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "기존 맞춤 트렌드",
          summary: "새로고침 이전에 조회된 데이터입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: null,
      has_next: false,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [firstPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      hasNextPage: false,
      hasCursorRecoveryFailed: false,
      error: null,
      restart: restartMock,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    // 1. 새로고침 전 기존 목록과 Refresh 상태를 확인한다.
    expect(screen.getByText("기존 맞춤 트렌드")).toBeTruthy();

    expect(screen.getByTestId("personalized-trend-list")).toHaveProp(
      "refreshing",
      false,
    );

    // 2. 사용자가 Pull-to-refresh를 실행한다.
    await fireEvent(screen.getByTestId("personalized-trend-list"), "refresh");

    expect(restartMock).toHaveBeenCalledTimes(1);

    // 3. restart()가 완료되지 않은 동안
    //    기존 TrendCard를 그대로 유지한다.
    expect(screen.getByText("기존 맞춤 트렌드")).toBeTruthy();

    // 4. 새로고침 진행 중임을 표시한다.
    expect(screen.getByTestId("personalized-trend-list")).toHaveProp(
      "refreshing",
      true,
    );

    // 5. 전체 화면 Loading으로 바뀌지 않는다.
    expect(
      screen.queryByText("관심사에 맞는 트렌드를 불러오고 있습니다."),
    ).toBeNull();

    // 6. 대기 중이던 restart()를 완료한다.
    await act(async () => {
      resolveRestart();
      await pendingRestart;
    });

    // 7. 완료 후 Refresh Indicator를 해제한다.
    await waitFor(() => {
      expect(screen.getByTestId("personalized-trend-list")).toHaveProp(
        "refreshing",
        false,
      );
    });

    // 8. 기존 Navigation에는 영향을 주지 않는다.
    expect(navigationMock.navigate).not.toHaveBeenCalled();
  });

  test("같은 렌더링 구간에서 연속 Refresh가 발생해도 restart를 한 번만 호출한다", async () => {
    let resolveRestart!: () => void;

    const pendingRestart = new Promise<void>((resolve) => {
      resolveRestart = resolve;
    });

    const restartMock = jest.fn(() => pendingRestart);

    const firstPage: TrendListData = {
      items: [
        {
          trend_id: 101,
          title: "기존 맞춤 트렌드",
          summary: "첫 페이지 데이터입니다.",
          thumbnail_url: null,
          last_collected_at: "2026-10-01T09:00:00Z",
          categories: [],
          latest_source: null,
        },
      ],
      next_cursor: "NEXT_CURSOR",
      has_next: true,
    };

    mockedUsePersonalizedTrends.mockReturnValue({
      data: {
        pages: [firstPage],
        pageParams: [undefined],
      },
      isPending: false,
      isError: false,
      isFetching: false,
      isFetchingNextPage: false,
      isFetchNextPageError: false,
      hasNextPage: true,
      hasCursorRecoveryFailed: false,
      error: null,
      restart: restartMock,
    } as unknown as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    const list = screen.getByTestId("personalized-trend-list");

    expect(list).toHaveProp("refreshing", false);

    // 동일한 React 렌더링 구간에서 이벤트가
    // 연속 발생하는 상황을 재현한다.
    const onRefresh = list.props.onRefresh as () => void;

    await act(async () => {
      onRefresh();
      onRefresh();
    });

    try {
      // 아직 restart가 완료되지 않았다.
      expect(restartMock).toHaveBeenCalledTimes(1);

      // 화면은 Refresh 진행 중 상태여야 한다.
      expect(screen.getByTestId("personalized-trend-list")).toHaveProp(
        "refreshing",
        true,
      );

      // 기존 카드도 유지되어야 한다.
      expect(screen.getByText("기존 맞춤 트렌드")).toBeTruthy();
    } finally {
      // RED가 발생하더라도 대기 중인 요청을 정리한다.
      await act(async () => {
        resolveRestart();
        await pendingRestart;
      });
    }
  });

  test("로그아웃 진행 중에는 버튼을 비활성화하고 중복 요청을 차단한다", async () => {
    let resolveLogout!: () => void;

    const pendingLogout = new Promise<void>((resolve) => {
      resolveLogout = resolve;
    });

    const logoutMock = jest.fn(() => pendingLogout);

    // 기존 Auth Mock의 세션 상태를 유지하면서 logout만 교체한다.
    mockedUseAuth.mockReturnValue({
      ...mockedUseAuth(),
      logout: logoutMock,
    });

    mockedUsePersonalizedTrends.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      isFetching: true,
    } as ReturnType<typeof usePersonalizedTrends>);

    await render(
      <PersonalizedMainScreen navigation={navigationMock} route={routeMock} />,
    );

    const logoutButton = screen.getByRole("button", {
      name: "로그아웃",
    });

    // 최초에는 누를 수 있다.
    expect(logoutButton).toHaveProp(
      "accessibilityState",
      expect.objectContaining({
        disabled: false,
        busy: false,
      }),
    );

    // 로그아웃 실행
    await fireEvent.press(logoutButton);

    expect(logoutMock).toHaveBeenCalledTimes(1);

    // 요청이 완료되지 않은 동안 버튼을 비활성화한다.
    const pendingButton = screen.getByRole("button", {
      name: "로그아웃",
    });

    expect(pendingButton).toHaveProp(
      "accessibilityState",
      expect.objectContaining({
        disabled: true,
        busy: true,
      }),
    );

    // 중복 요청을 허용하지 않는다.
    await fireEvent.press(pendingButton);

    expect(logoutMock).toHaveBeenCalledTimes(1);

    // 테스트 종료 전 대기 중인 요청을 정리한다.
    await act(async () => {
      resolveLogout();
      await pendingLogout;
    });
  });
});
