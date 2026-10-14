import { fireEvent, render } from "@testing-library/react-native";
import type { ComponentProps } from "react";

import { useAuth } from "../../src/app/providers/AuthProvider";
import { useLogin } from "../../src/features/auth/hooks/useLogin";
import { LoginScreen } from "../../src/features/auth/screens/LoginScreen";

jest.mock("../../src/app/providers/AuthProvider", () => ({
  useAuth: jest.fn(),
}));

jest.mock("../../src/features/auth/hooks/useLogin", () => ({
  useLogin: jest.fn(),
}));

const mockedUseAuth = jest.mocked(useAuth);
const mockedUseLogin = jest.mocked(useLogin);
const loginMutateMock = jest.fn();
const establishSessionMock = jest.fn();

type LoginScreenProps = ComponentProps<typeof LoginScreen>;

const navigationMock = {
  navigate: jest.fn(),
} as unknown as LoginScreenProps["navigation"];

const routeMock = {
  key: "Login-password-visibility-test",
  name: "Login",
} as LoginScreenProps["route"];

describe("LoginScreen password visibility", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    mockedUseAuth.mockReturnValue({
      authState: { status: "UNAUTHENTICATED" },
      establishSession: establishSessionMock,
      restoreSession: jest.fn(),
      revalidateSession: jest.fn(),
      completeInterestSelection: jest.fn(),
      logout: jest.fn(),
    } as unknown as ReturnType<typeof useAuth>);

    mockedUseLogin.mockReturnValue({
      mutate: loginMutateMock,
      isPending: false,
    } as unknown as ReturnType<typeof useLogin>);
  });

  test("기본 숨김 상태에서 보기/숨기기 전환이 비밀번호 값을 보존한다", async () => {
    const view = await render(
      <LoginScreen navigation={navigationMock} route={routeMock} />,
    );

    const passwordField = view.getByLabelText("비밀번호");
    await fireEvent.changeText(passwordField, "pass1234");

    expect(passwordField.props.secureTextEntry).toBe(true);

    await fireEvent.press(
      view.getByRole("button", { name: "비밀번호 보기" }),
    );

    expect(view.getByLabelText("비밀번호").props.secureTextEntry).toBe(false);
    expect(view.getByLabelText("비밀번호").props.value).toBe("pass1234");

    await fireEvent.press(
      view.getByRole("button", { name: "비밀번호 숨기기" }),
    );

    expect(view.getByLabelText("비밀번호").props.secureTextEntry).toBe(true);
    expect(view.getByLabelText("비밀번호").props.value).toBe("pass1234");
  });

  test("비밀번호 표시 상태가 로그인 요청 페이로드를 변경하지 않는다", async () => {
    const view = await render(
      <LoginScreen navigation={navigationMock} route={routeMock} />,
    );

    await fireEvent.changeText(
      view.getByLabelText("아이디"),
      "trend_user",
    );
    await fireEvent.changeText(
      view.getByLabelText("비밀번호"),
      "pass1234",
    );

    await fireEvent.press(
      view.getByRole("button", { name: "비밀번호 보기" }),
    );
    await fireEvent.press(
      view.getByRole("button", { name: "로그인" }),
    );

    expect(loginMutateMock).toHaveBeenCalledWith(
      { login_id: "trend_user", password: "pass1234" },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
  });
});
