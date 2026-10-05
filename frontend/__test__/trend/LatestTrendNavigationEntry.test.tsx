import {
    fireEvent,
    render,
} from "@testing-library/react-native";
import type {
    ComponentProps,
} from "react";

import {
    useAuth,
} from "../../src/app/providers/AuthProvider";
import {
    MainPlaceholderScreen,
} from "../../src/app/screens/MainPlaceholderScreen";
import {
    useLogin,
} from "../../src/features/auth/hooks/useLogin";
import {
    LoginScreen,
} from "../../src/features/auth/screens/LoginScreen";

jest.mock(
  "../../src/app/providers/AuthProvider",
  () => ({
    useAuth: jest.fn(),
  }),
);

jest.mock(
  "../../src/features/auth/hooks/useLogin",
  () => ({
    useLogin: jest.fn(),
  }),
);

jest.setTimeout(20_000);

const mockedUseAuth =
  jest.mocked(useAuth);

const mockedUseLogin =
  jest.mocked(useLogin);

const navigateMock =
  jest.fn();

const logoutMock =
  jest.fn(
    async (): Promise<void> =>
      undefined,
  );

const establishSessionMock =
  jest.fn(
    async (): Promise<void> =>
      undefined,
  );

type LoginScreenProps =
  ComponentProps<typeof LoginScreen>;

type MainScreenProps =
  ComponentProps<
    typeof MainPlaceholderScreen
  >;

const loginNavigationMock = {
  navigate: navigateMock,
} as unknown as
  LoginScreenProps["navigation"];

const loginRouteMock = {
  key: "Login-test",
  name: "Login",
} as LoginScreenProps["route"];

const mainNavigationMock = {
  navigate: navigateMock,
} as unknown as
  MainScreenProps["navigation"];

const mainRouteMock = {
  key: "Main-test",
  name: "Main",
} as MainScreenProps["route"];

describe(
  "LatestTrend navigation entry",
  () => {
    beforeEach(() => {
      jest.clearAllMocks();

      mockedUseAuth.mockReset();
      mockedUseLogin.mockReset();

      navigateMock.mockReset();
      logoutMock.mockReset();
      establishSessionMock.mockReset();

      logoutMock.mockResolvedValue(
        undefined,
      );

      establishSessionMock
        .mockResolvedValue(
          undefined,
        );

      mockedUseLogin.mockReturnValue({
        mutate: jest.fn(),
        isPending: false,
      } as unknown as ReturnType<
        typeof useLogin
      >);
    });

    test(
      "비로그인 Login 화면에서 최신 트렌드 둘러보기를 누르면 LatestTrend로 이동한다",
      async () => {
        mockedUseAuth.mockReturnValue({
          authState: {
            status:
              "UNAUTHENTICATED",
          },
          establishSession:
            establishSessionMock,
          restoreSession:
            jest.fn(),
          revalidateSession:
            jest.fn(),
          completeInterestSelection:
            jest.fn(),
          logout:
            logoutMock,
        } as unknown as ReturnType<
          typeof useAuth
        >);

        const view = await render(
          <LoginScreen
            navigation={
              loginNavigationMock
            }
            route={
              loginRouteMock
            }
          />,
        );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name:
                "최신 트렌드 둘러보기",
            },
          ),
        );

        expect(
          navigateMock,
        ).toHaveBeenCalledTimes(
          1,
        );

        expect(
          navigateMock,
        ).toHaveBeenCalledWith(
          "LatestTrend",
        );
      },
    );

    test(
      "로그인 Main 화면에서 최신 트렌드 보기를 누르면 LatestTrend로 이동한다",
      async () => {
        mockedUseAuth.mockReturnValue({
          authState: {
            status:
              "AUTHENTICATED",
            session: {
              user: {
                user_id: 1,
                login_id:
                  "trend_user",
                name:
                  "테스트 사용자",
                status:
                  "ACTIVE",
              },
              has_selected_interests:
                true,
              next_step:
                "MAIN",
            },
          },
          establishSession:
            establishSessionMock,
          restoreSession:
            jest.fn(),
          revalidateSession:
            jest.fn(),
          completeInterestSelection:
            jest.fn(),
          logout:
            logoutMock,
        } as unknown as ReturnType<
          typeof useAuth
        >);

        const view = await render(
          <MainPlaceholderScreen
            navigation={
              mainNavigationMock
            }
            route={
              mainRouteMock
            }
          />,
        );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name:
                "최신 트렌드 보기",
            },
          ),
        );

        expect(
          navigateMock,
        ).toHaveBeenCalledTimes(
          1,
        );

        expect(
          navigateMock,
        ).toHaveBeenCalledWith(
          "LatestTrend",
        );
      },
    );
  },
);
