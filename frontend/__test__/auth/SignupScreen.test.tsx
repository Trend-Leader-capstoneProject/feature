import {
    act,
    fireEvent,
    render,
    waitFor,
} from "@testing-library/react-native";
import type {
    AxiosError,
} from "axios";
import type {
    ComponentProps,
} from "react";
import {
    Alert,
} from "react-native";

import {
    useAuth,
} from "../../src/app/providers/AuthProvider";
import {
    useCheckLoginId,
} from "../../src/features/auth/hooks/useCheckLoginId";
import {
    useSignup,
} from "../../src/features/auth/hooks/useSignup";
import {
    SignupScreen,
} from "../../src/features/auth/screens/SignupScreen";
import type {
    CheckLoginIdErrorResponse,
    CheckLoginIdResponse,
    SignupErrorResponse,
    SignupResponse,
} from "../../src/features/auth/types/auth";

jest.mock(
  "../../src/app/providers/AuthProvider",
  () => ({
    useAuth: jest.fn(),
  }),
);

jest.mock(
  "../../src/features/auth/hooks/useCheckLoginId",
  () => ({
    useCheckLoginId: jest.fn(),
  }),
);

jest.mock(
  "../../src/features/auth/hooks/useSignup",
  () => ({
    useSignup: jest.fn(),
  }),
);

const mockedUseAuth =
  jest.mocked(useAuth);

const mockedUseCheckLoginId =
  jest.mocked(useCheckLoginId);

const mockedUseSignup =
  jest.mocked(useSignup);

const checkLoginIdMutateMock =
  jest.fn();

const signupMutateAsyncMock =
  jest.fn();

const establishSessionMock =
  jest.fn();

const goBackMock =
  jest.fn();

const VALID_LOGIN_ID =
  "trend_new_user";

const CHANGED_LOGIN_ID =
  "trend_new_user2";

const VALID_PASSWORD =
  "trend-password-123";

const VALID_NAME =
  "테스트 사용자";

const VALID_EMAIL =
  "trend@example.com";

const SIGNUP_RESPONSE: SignupResponse = {
  access_token: "SIGNUP_ACCESS_TOKEN",
  token_type: "Bearer",
  user: {
    user_id: 10,
    login_id: VALID_LOGIN_ID,
    name: VALID_NAME,
    status: "ACTIVE",
  },
  has_selected_interests: false,
  next_step: "INTEREST_SELECTION",
};

type SignupScreenComponentProps =
  ComponentProps<typeof SignupScreen>;

type SignupRenderResult =
  Awaited<ReturnType<typeof render>>;

const navigationMock = {
  goBack: goBackMock,
} as unknown as
  SignupScreenComponentProps["navigation"];

const routeMock = {
  key: "Signup-test",
  name: "Signup",
} as SignupScreenComponentProps["route"];

type CheckLoginIdCallbacks = {
  onSuccess?: (
    result: CheckLoginIdResponse,
  ) => void;
  onError?: (
    error: AxiosError<
      CheckLoginIdErrorResponse
    >,
  ) => void;
};

let rendered:
  SignupRenderResult | null = null;

function getRendered():
  SignupRenderResult {
  if (rendered === null) {
    throw new Error(
      "SignupScreen이 아직 render되지 않았습니다.",
    );
  }

  return rendered;
}

async function renderSignupScreen():
  Promise<SignupRenderResult> {
  rendered = await render(
    <SignupScreen
      navigation={navigationMock}
      route={routeMock}
    />,
  );

  return rendered;
}

function getCheckLoginIdCallbacks():
  CheckLoginIdCallbacks {
  const calls =
    checkLoginIdMutateMock.mock.calls;

  const call =
    calls[calls.length - 1];

  if (!call) {
    throw new Error(
      "아이디 중복 확인 Mutation이 호출되지 않았습니다.",
    );
  }

  return call[1] as
    CheckLoginIdCallbacks;
}

async function confirmLoginIdAvailable(
  loginId: string = VALID_LOGIN_ID,
): Promise<void> {
  const view = getRendered();

  await fireEvent.changeText(
    view.getByLabelText("아이디"),
    loginId,
  );

  await fireEvent.press(
    view.getByRole("button", {
      name: "중복 확인",
    }),
  );

  expect(
    checkLoginIdMutateMock,
  ).toHaveBeenLastCalledWith(
    {
      login_id: loginId,
    },
    expect.any(Object),
  );

  const callbacks =
    getCheckLoginIdCallbacks();

  await act(() => {
    callbacks.onSuccess?.({
      login_id: loginId,
      is_available: true,
      reason: null,
    });
  });

  await waitFor(() => {
    expect(
      view.getByText(
        "사용 가능한 아이디입니다.",
      ),
    ).toBeTruthy();
  });
}

async function fillRemainingValidFields({
  email = VALID_EMAIL,
}: {
  email?: string;
} = {}): Promise<void> {
  const view = getRendered();

  await fireEvent.changeText(
    view.getByLabelText("비밀번호"),
    VALID_PASSWORD,
  );

  await fireEvent.changeText(
    view.getByLabelText(
      "비밀번호 확인",
    ),
    VALID_PASSWORD,
  );

  await fireEvent.changeText(
    view.getByLabelText("이름"),
    VALID_NAME,
  );

  await fireEvent.changeText(
    view.getByLabelText("이메일"),
    email,
  );
}

async function prepareValidSignupForm():
  Promise<void> {
  await renderSignupScreen();

  await confirmLoginIdAvailable();

  await fillRemainingValidFields();
}

function createSignupAxiosError(
  responseData: SignupErrorResponse,
): AxiosError<SignupErrorResponse> {
  return {
    isAxiosError: true,
    response: {
      status: responseData.statusCode,
      data: responseData,
    },
  } as AxiosError<SignupErrorResponse>;
}

function createSignupLoginIdConflictError():
  AxiosError<SignupErrorResponse> {
  return createSignupAxiosError({
    success: false,
    statusCode: 409,
    message:
      "이미 존재하는 데이터입니다.",
    data: {
      field: "login_id",
      reason:
        "DUPLICATED_LOGIN_ID",
    },
  });
}

function createSignupEmailConflictError():
  AxiosError<SignupErrorResponse> {
  return createSignupAxiosError({
    success: false,
    statusCode: 409,
    message:
      "이미 존재하는 데이터입니다.",
    data: {
      field: "email",
      reason: "DUPLICATED_EMAIL",
    },
  });
}

function createSignupValidationError():
  AxiosError<SignupErrorResponse> {
  return createSignupAxiosError({
    success: false,
    statusCode: 422,
    message:
      "요청 데이터가 올바르지 않습니다.",
    data: {
      errors: [
        {
          field: "body.name",
          message:
            "Value error",
          type: "value_error",
        },
        {
          field: "body.email",
          message:
            "Value is not a valid email address",
          type: "value_error",
        },
      ],
    },
  });
}

function createSignupServerError():
  AxiosError<SignupErrorResponse> {
  return createSignupAxiosError({
    success: false,
    statusCode: 500,
    message:
      "서버 오류가 발생했습니다.",
    data: null,
  });
}

function createSignupNetworkError():
  AxiosError<SignupErrorResponse> {
  return {
    isAxiosError: true,
    message: "Network Error",
  } as AxiosError<SignupErrorResponse>;
}

describe(
  "SignupScreen signup flow",
  () => {
    let alertSpy:
      jest.SpyInstance;

    beforeEach(() => {
      jest.resetAllMocks();

      rendered = null;

      establishSessionMock
        .mockResolvedValue(
          undefined,
        );

      mockedUseAuth.mockReturnValue({
        authState: {
          status:
            "UNAUTHENTICATED",
        },
        establishSession:
          establishSessionMock,
        restoreSession:
          jest.fn(
            async (): Promise<void> =>
              undefined,
          ),
        revalidateSession:
          jest.fn(
            async (): Promise<void> =>
              undefined,
          ),
        completeInterestSelection:
          jest.fn(),
        logout:
          jest.fn(
            async (): Promise<void> =>
              undefined,
          ),
      } as ReturnType<typeof useAuth>);

      mockedUseCheckLoginId
        .mockReturnValue({
          mutate:
            checkLoginIdMutateMock,
          isPending: false,
        } as unknown as
          ReturnType<
            typeof useCheckLoginId
          >);

      mockedUseSignup.mockReturnValue({
        mutateAsync:
          signupMutateAsyncMock,
        isPending: false,
      } as unknown as
        ReturnType<typeof useSignup>);

      alertSpy = jest
        .spyOn(
          Alert,
          "alert",
        )
        .mockImplementation(
          () => undefined,
        );
    });

    afterEach(() => {
      alertSpy.mockRestore();
    });

    test(
      "사용 가능 확인 후 아이디를 변경하면 기존 확인 상태를 무효화한다",
      async () => {
        const view =
          await renderSignupScreen();

        await confirmLoginIdAvailable();

        expect(
          view.getByText(
            "사용 가능한 아이디입니다.",
          ),
        ).toBeTruthy();

        await fireEvent.changeText(
          view.getByLabelText(
            "아이디",
          ),
          CHANGED_LOGIN_ID,
        );

        expect(
          view.queryByText(
            "사용 가능한 아이디입니다.",
          ),
        ).toBeNull();

        await fillRemainingValidFields();

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name: "회원가입",
            },
          ),
        );

        await waitFor(() => {
          expect(
            view.getByText(
              "아이디 중복 확인을 완료해 주세요.",
            ),
          ).toBeTruthy();
        });

        expect(
          signupMutateAsyncMock,
        ).not.toHaveBeenCalled();
      },
    );

    test(
      "중복 확인 요청 후 아이디가 변경되면 이전 아이디의 늦은 응답을 무시한다",
      async () => {
        const view =
          await renderSignupScreen();

        await fireEvent.changeText(
          view.getByLabelText(
            "아이디",
          ),
          VALID_LOGIN_ID,
        );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name: "중복 확인",
            },
          ),
        );

        const callbacks =
          getCheckLoginIdCallbacks();

        await fireEvent.changeText(
          view.getByLabelText(
            "아이디",
          ),
          CHANGED_LOGIN_ID,
        );

        await act(() => {
          callbacks.onSuccess?.({
            login_id:
              VALID_LOGIN_ID,
            is_available: true,
            reason: null,
          });
        });

        expect(
          view.queryByText(
            "사용 가능한 아이디입니다.",
          ),
        ).toBeNull();

        expect(
          view
            .getByLabelText(
              "아이디",
            )
            .props.value,
        ).toBe(
          CHANGED_LOGIN_ID,
        );
      },
    );

    test(
      "Signup에서 login_id 409가 발생하면 아이디 중복 오류를 표시한다",
      async () => {
        await prepareValidSignupForm();

        const view =
          getRendered();

        signupMutateAsyncMock
          .mockRejectedValueOnce(
            createSignupLoginIdConflictError(),
          );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name: "회원가입",
            },
          ),
        );

        await waitFor(() => {
          expect(
            signupMutateAsyncMock,
          ).toHaveBeenCalledTimes(
            1,
          );
        });

        await waitFor(() => {
          expect(
            view.getByText(
              "이미 사용 중인 아이디입니다.",
            ),
          ).toBeTruthy();
        });

        expect(
          establishSessionMock,
        ).not.toHaveBeenCalled();
      },
    );

    test(
      "Signup에서 email 409가 발생하면 이메일 중복 오류를 표시한다",
      async () => {
        await prepareValidSignupForm();

        const view =
          getRendered();

        signupMutateAsyncMock
          .mockRejectedValueOnce(
            createSignupEmailConflictError(),
          );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name: "회원가입",
            },
          ),
        );

        await waitFor(() => {
          expect(
            view.getByText(
              "이미 사용 중인 이메일입니다.",
            ),
          ).toBeTruthy();
        });

        expect(
          signupMutateAsyncMock,
        ).toHaveBeenCalledTimes(1);

        expect(
          establishSessionMock,
        ).not.toHaveBeenCalled();
      },
    );

    test(
      "Signup 422의 body 필드를 해당 입력 필드 오류로 매핑한다",
      async () => {
        await prepareValidSignupForm();

        const view =
          getRendered();

        signupMutateAsyncMock
          .mockRejectedValueOnce(
            createSignupValidationError(),
          );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name: "회원가입",
            },
          ),
        );

        await waitFor(() => {
          expect(
            view.getByText(
              "이름을 확인해 주세요.",
            ),
          ).toBeTruthy();

          expect(
            view.getByText(
              "올바른 이메일 형식을 입력해 주세요.",
            ),
          ).toBeTruthy();
        });

        expect(
          establishSessionMock,
        ).not.toHaveBeenCalled();
      },
    );

    test(
      "Signup 네트워크 오류 시 입력값을 유지하고 네트워크 오류를 표시한다",
      async () => {
        await prepareValidSignupForm();

        const view =
          getRendered();

        signupMutateAsyncMock
          .mockRejectedValueOnce(
            createSignupNetworkError(),
          );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name: "회원가입",
            },
          ),
        );

        await waitFor(() => {
          expect(
            view.getByText(
              "서버에 연결할 수 없습니다. 네트워크 상태를 확인해 주세요.",
            ),
          ).toBeTruthy();
        });

        expect(
          view
            .getByLabelText(
              "비밀번호",
            )
            .props.value,
        ).toBe(
          VALID_PASSWORD,
        );

        expect(
          view
            .getByLabelText(
              "이메일",
            )
            .props.value,
        ).toBe(
          VALID_EMAIL,
        );

        expect(
          establishSessionMock,
        ).not.toHaveBeenCalled();
      },
    );

    test(
      "Signup 500 오류 시 서버 오류 메시지를 표시한다",
      async () => {
        await prepareValidSignupForm();

        const view =
          getRendered();

        signupMutateAsyncMock
          .mockRejectedValueOnce(
            createSignupServerError(),
          );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name: "회원가입",
            },
          ),
        );

        await waitFor(() => {
          expect(
            view.getByText(
              "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            ),
          ).toBeTruthy();
        });

        expect(
          establishSessionMock,
        ).not.toHaveBeenCalled();
      },
    );

    test(
      "Signup 성공 시 응답으로 establishSession을 호출하고 비밀번호 state를 비운다",
      async () => {
        await prepareValidSignupForm();

        const view =
          getRendered();

        signupMutateAsyncMock
          .mockResolvedValueOnce(
            SIGNUP_RESPONSE,
          );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name: "회원가입",
            },
          ),
        );

        await waitFor(() => {
          expect(
            signupMutateAsyncMock,
          ).toHaveBeenCalledWith({
            login_id:
              VALID_LOGIN_ID,
            password:
              VALID_PASSWORD,
            password_confirm:
              VALID_PASSWORD,
            name: VALID_NAME,
            email: VALID_EMAIL,
          });
        });

        await waitFor(() => {
          expect(
            establishSessionMock,
          ).toHaveBeenCalledWith(
            SIGNUP_RESPONSE,
          );
        });

        expect(
          establishSessionMock,
        ).toHaveBeenCalledTimes(1);

        await waitFor(() => {
          expect(
            view
              .getByLabelText(
                "비밀번호",
              )
              .props.value,
          ).toBe("");

          expect(
            view
              .getByLabelText(
                "비밀번호 확인",
              )
              .props.value,
          ).toBe("");
        });

        expect(
          goBackMock,
        ).not.toHaveBeenCalled();

        expect(
          alertSpy,
        ).not.toHaveBeenCalled();
      },
    );

    test(
      "Signup 성공 후 establishSession 실패 시 Signup을 재호출하지 않고 로그인 복귀 안내를 표시한다",
      async () => {
        await prepareValidSignupForm();

        const view =
          getRendered();

        signupMutateAsyncMock
          .mockResolvedValueOnce(
            SIGNUP_RESPONSE,
          );

        establishSessionMock
          .mockRejectedValueOnce(
            new Error(
              "SecureStore write failed",
            ),
          );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name: "회원가입",
            },
          ),
        );

        await waitFor(() => {
          expect(
            alertSpy,
          ).toHaveBeenCalledTimes(1);
        });

        expect(
          signupMutateAsyncMock,
        ).toHaveBeenCalledTimes(1);

        expect(
          establishSessionMock,
        ).toHaveBeenCalledTimes(1);

        expect(
          alertSpy,
        ).toHaveBeenCalledWith(
          "회원가입 완료",
          "회원가입은 완료되었지만 로그인 정보를 저장하지 못했습니다.\n로그인 화면에서 다시 로그인해 주세요.",
          expect.any(Array),
          {
            cancelable: false,
          },
        );

        /*
         * 이미 Signup API 자체는 성공했으므로
         * 이후에는 재가입 요청을 허용하지 않는다.
         */
        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name: "회원가입",
            },
          ),
        );

        expect(
          signupMutateAsyncMock,
        ).toHaveBeenCalledTimes(1);

        const alertCall =
          alertSpy.mock.calls[0];

        const confirmButton =
          alertCall?.[2]?.[0];

        if (!confirmButton) {
          throw new Error(
            "회원가입 완료 Alert의 확인 버튼이 없습니다.",
          );
        }

        await act(() => {
          confirmButton.onPress?.();
        });

        expect(
          goBackMock,
        ).toHaveBeenCalledTimes(1);
      },
    );

    test(
      "비밀번호 보기/숨기기는 입력값을 변경하지 않고 secureTextEntry만 전환한다",
      async () => {
        const view =
          await renderSignupScreen();

        await fireEvent.changeText(
          view.getByLabelText(
            "비밀번호",
          ),
          VALID_PASSWORD,
        );

        await fireEvent.changeText(
          view.getByLabelText(
            "비밀번호 확인",
          ),
          VALID_PASSWORD,
        );

        expect(
          view
            .getByLabelText(
              "비밀번호",
            )
            .props.secureTextEntry,
        ).toBe(true);

        expect(
          view
            .getByLabelText(
              "비밀번호 확인",
            )
            .props.secureTextEntry,
        ).toBe(true);

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name:
                "비밀번호 보기",
            },
          ),
        );

        expect(
          view
            .getByLabelText(
              "비밀번호",
            )
            .props.secureTextEntry,
        ).toBe(false);

        expect(
          view
            .getByLabelText(
              "비밀번호",
            )
            .props.value,
        ).toBe(
          VALID_PASSWORD,
        );

        /*
         * 두 입력의 표시 상태는
         * 서로 독립적이어야 한다.
         */
        expect(
          view
            .getByLabelText(
              "비밀번호 확인",
            )
            .props.secureTextEntry,
        ).toBe(true);

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name:
                "비밀번호 확인 보기",
            },
          ),
        );

        expect(
          view
            .getByLabelText(
              "비밀번호 확인",
            )
            .props.secureTextEntry,
        ).toBe(false);

        expect(
          view
            .getByLabelText(
              "비밀번호 확인",
            )
            .props.value,
        ).toBe(
          VALID_PASSWORD,
        );

        await fireEvent.press(
          view.getByRole(
            "button",
            {
              name:
                "비밀번호 숨기기",
            },
          ),
        );

        expect(
          view
            .getByLabelText(
              "비밀번호",
            )
            .props.secureTextEntry,
        ).toBe(true);

        expect(
          view
            .getByLabelText(
              "비밀번호",
            )
            .props.value,
        ).toBe(
          VALID_PASSWORD,
        );
      },
    );
  },
);
