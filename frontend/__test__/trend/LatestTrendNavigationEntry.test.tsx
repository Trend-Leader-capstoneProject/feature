import { fireEvent, render } from "@testing-library/react-native";
import type { ComponentProps } from "react";

import { useAuth } from "../../src/app/providers/AuthProvider";
import { PersonalizedMainScreen } from "../../src/app/screens/PersonalizedMainScreen";
import { useLogin } from "../../src/features/auth/hooks/useLogin";
import { LoginScreen } from "../../src/features/auth/screens/LoginScreen";
import { usePersonalizedTrends } from "../../src/features/trend/hooks/usePersonalizedTrends";

jest.mock("../../src/app/providers/AuthProvider", () => ({
  useAuth: jest.fn(),
}));

jest.mock("../../src/features/auth/hooks/useLogin", () => ({
  useLogin: jest.fn(),
}));

jest.mock("../../src/features/trend/hooks/usePersonalizedTrends", () => ({
  usePersonalizedTrends: jest.fn(),
}));

jest.setTimeout(20_000);

const mockedUseAuth = jest.mocked(useAuth);

const mockedUseLogin = jest.mocked(useLogin);

const navigateMock = jest.fn();

const logoutMock = jest.fn(async (): Promise<void> => undefined);

const establishSessionMock = jest.fn(async (): Promise<void> => undefined);

const mockedUsePersonalizedTrends = jest.mocked(usePersonalizedTrends);

type LoginScreenProps = ComponentProps<typeof LoginScreen>;

type MainScreenProps = ComponentProps<typeof PersonalizedMainScreen>;

const loginNavigationMock = {
  navigate: navigateMock,
} as unknown as LoginScreenProps["navigation"];

const loginRouteMock = {
  key: "Login-test",
  name: "Login",
} as LoginScreenProps["route"];

const mainNavigationMock = {
  navigate: navigateMock,
} as unknown as MainScreenProps["navigation"];

const mainRouteMock = {
  key: "Main-test",
  name: "Main",
} as MainScreenProps["route"];

describe("LatestTrend navigation entry", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    mockedUsePersonalizedTrends.mockReset();

    mockedUsePersonalizedTrends.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      isFetching: true,
    } as ReturnType<typeof usePersonalizedTrends>);

    mockedUseAuth.mockReset();
    mockedUseLogin.mockReset();

    navigateMock.mockReset();
    logoutMock.mockReset();
    establishSessionMock.mockReset();

    logoutMock.mockResolvedValue(undefined);

    establishSessionMock.mockResolvedValue(undefined);

    mockedUseLogin.mockReturnValue({
      mutate: jest.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useLogin>);
  });

  test("비로그인 Login 화면에서 최신 트렌드 둘러보기를 누르면 LatestTrend로 이동한다", async () => {
    mockedUseAuth.mockReturnValue({
      authState: {
        status: "UNAUTHENTICATED",
      },
      establishSession: establishSessionMock,
      restoreSession: jest.fn(),
      revalidateSession: jest.fn(),
      completeInterestSelection: jest.fn(),
      logout: logoutMock,
    } as unknown as ReturnType<typeof useAuth>);

    const view = await render(
      <LoginScreen navigation={loginNavigationMock} route={loginRouteMock} />,
    );

    await fireEvent.press(
      view.getByRole("button", {
        name: "최신 트렌드 둘러보기",
      }),
    );

    expect(navigateMock).toHaveBeenCalledTimes(1);

    expect(navigateMock).toHaveBeenCalledWith("LatestTrend");
  });

  test("로그인 Main 화면에서 최신 트렌드 보기를 누르면 LatestTrend로 이동한다", async () => {
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
      establishSession: establishSessionMock,
      restoreSession: jest.fn(),
      revalidateSession: jest.fn(),
      completeInterestSelection: jest.fn(),
      logout: logoutMock,
    } as unknown as ReturnType<typeof useAuth>);

    const view = await render(
      <PersonalizedMainScreen
        navigation={mainNavigationMock}
        route={mainRouteMock}
      />,
    );

    await fireEvent.press(
      view.getByRole("button", {
        name: "최신 트렌드 보기",
      }),
    );

    expect(navigateMock).toHaveBeenCalledTimes(1);

    expect(navigateMock).toHaveBeenCalledWith("LatestTrend");
  });
});
