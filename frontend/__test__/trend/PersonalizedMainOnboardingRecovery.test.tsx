
import {
    QueryClient,
    QueryClientProvider,
} from "@tanstack/react-query";
import {
    act,
    render,
    screen,
    waitFor,
} from "@testing-library/react-native";
import type {
    ComponentProps,
    PropsWithChildren,
} from "react";
import { Text } from "react-native";

import { AppNavigator } from "../../src/app/navigation/AppNavigator";
import { OnboardingNavigator } from "../../src/app/navigation/OnboardingNavigator";
import { RootNavigator } from "../../src/app/navigation/RootNavigator";
import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { MainPlaceholderScreen } from "../../src/app/screens/MainPlaceholderScreen";
import { getAuthSession } from "../../src/features/auth/api/getAuthSession";
import type { SessionResponse } from "../../src/features/auth/types/auth";
import { usePersonalizedTrends } from "../../src/features/trend/hooks/usePersonalizedTrends";
import { registerAuthFailureHandler } from "../../src/shared/handler/authFailureHandler";
import { getAccessToken } from "../../src/shared/storage/tokenStorage";

// 실제 RootNavigator 분기는 유지하고,
// NavigationContainer의 Native 연결만 대체한다.
jest.mock("@react-navigation/native", () => ({
  NavigationContainer: ({
    children,
  }: PropsWithChildren) => children,
}));

jest.mock("../../src/app/navigation/AppNavigator", () => ({
  AppNavigator: jest.fn(),
}));

jest.mock(
  "../../src/app/navigation/OnboardingNavigator",
  () => ({
    OnboardingNavigator: jest.fn(),
  }),
);

jest.mock("../../src/app/navigation/AuthNavigator", () => ({
  AuthNavigator: jest.fn(() => null),
}));

jest.mock("../../src/features/auth/api/getAuthSession", () => ({
  getAuthSession: jest.fn(),
}));

jest.mock("../../src/features/trend/hooks/usePersonalizedTrends", () => ({
  usePersonalizedTrends: jest.fn(),
}));

jest.mock("../../src/shared/storage/tokenStorage", () => ({
  getAccessToken: jest.fn(),
  saveAccessToken: jest.fn(),
  deleteAccessToken: jest.fn(),
}));

jest.mock("../../src/shared/handler/authFailureHandler", () => ({
  registerAuthFailureHandler: jest.fn(),
}));

jest.mock("../../src/shared/handler/authRequestGate", () => ({
  allowAuthenticatedRequests: jest.fn(),
  blockAuthenticatedRequests: jest.fn(),
}));

const mockedGetAuthSession = jest.mocked(getAuthSession);
const mockedGetAccessToken = jest.mocked(getAccessToken);
const mockedUsePersonalizedTrends = jest.mocked(
  usePersonalizedTrends,
);
const mockedAppNavigator = jest.mocked(AppNavigator);
const mockedOnboardingNavigator = jest.mocked(
  OnboardingNavigator,
);
const mockedRegisterAuthFailureHandler = jest.mocked(
  registerAuthFailureHandler,
);

type MainProps = ComponentProps<typeof MainPlaceholderScreen>;

const navigateMock = jest.fn();

const navigationMock = {
  navigate: navigateMock,
} as unknown as MainProps["navigation"];

const routeMock = {
  key: "Main-integration-test",
  name: "Main",
} as MainProps["route"];

const MAIN_SESSION: SessionResponse = {
  user: {
    user_id: 1,
    login_id: "trend_user",
    name: "테스트 사용자",
    status: "ACTIVE",
  },
  has_selected_interests: true,
  next_step: "MAIN",
};

const INTEREST_SELECTION_SESSION: SessionResponse = {
  ...MAIN_SESSION,
  has_selected_interests: false,
  next_step: "INTEREST_SELECTION",
};

function createDeferred<T>() {
  let resolvePromise: ((value: T) => void) | null = null;

  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });

  return {
    promise,
    resolve(value: T): void {
      if (!resolvePromise) {
        throw new Error("Deferred Promise가 초기화되지 않았습니다.");
      }

      resolvePromise(value);
    },
  };
}

describe("Personalized Main onboarding recovery", () => {
  beforeEach(() => {
    jest.resetAllMocks();

    mockedGetAccessToken.mockResolvedValue("TOKEN_A");

    mockedRegisterAuthFailureHandler.mockImplementation(
      () => () => undefined,
    );

    // AppNavigator 대신 실제 Main 화면을 렌더링한다.
    mockedAppNavigator.mockImplementation(() => (
      <MainPlaceholderScreen
        navigation={navigationMock}
        route={routeMock}
      />
    ));

    // OnboardingNavigator에 진입했는지 식별한다.
    mockedOnboardingNavigator.mockImplementation(() => (
      <Text>온보딩 전환 확인</Text>
    ));

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
  });

  test(
    "409 발생 후 Session이 INTEREST_SELECTION으로 변경되면 RootNavigator가 Onboarding으로 전환한다",
    async () => {
      const deferredSession = createDeferred<SessionResponse>();

      // 최초 앱 진입: MAIN
      mockedGetAuthSession
        .mockResolvedValueOnce(MAIN_SESSION)
        // 409 이후 재검증: 응답을 보류한다.
        .mockImplementationOnce(
          () => deferredSession.promise,
        );

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
          <AuthProvider>
            <RootNavigator />
          </AuthProvider>
        </QueryClientProvider>,
      );

      // 1. MAIN 진입 후 409를 감지하고 Session 재검증을 시작한다.
      await waitFor(() => {
        expect(mockedGetAuthSession).toHaveBeenCalledTimes(2);
      });

      expect(mockedAppNavigator).toHaveBeenCalled();

      expect(
        screen.getByText(
          "관심사 설정 상태를 확인하고 있습니다.",
        ),
      ).toBeTruthy();

      // 2. 서버의 재검증 응답이 INTEREST_SELECTION으로 변경된다.
      await act(async () => {
        deferredSession.resolve(INTEREST_SELECTION_SESSION);
      });

      // 3. 실제 RootNavigator가 Onboarding으로 전환한다.
      await waitFor(() => {
        expect(
          screen.getByText("온보딩 전환 확인"),
        ).toBeTruthy();
      });

      // 4. 기존 Main 화면은 제거되어야 한다.
      expect(
        screen.queryByText("Trend Leader"),
      ).toBeNull();

      expect(
        screen.queryByText(
          "관심사 설정 상태가 일치하지 않습니다.",
        ),
      ).toBeNull();

      // 5. Main에서 직접 navigate 하지 않는다.
      expect(navigateMock).not.toHaveBeenCalled();

      // 6. 재검증을 자동으로 반복하지 않는다.
      expect(mockedGetAuthSession).toHaveBeenCalledTimes(2);
    },
  );
});
