import { useNavigation } from "@react-navigation/native";
import {
    act,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/react-native";
import type { AxiosError } from "axios";
import { Alert } from "react-native";

import { useAuth } from "../../src/app/providers/AuthProvider";
import { useCategories } from "../../src/features/interest/hooks/useCategories";
import { useUpdateInterests } from "../../src/features/interest/hooks/useUpdateInterests";
import { useUserInterests } from "../../src/features/interest/hooks/useUserInterests";
import { InterestEditScreen } from "../../src/features/interest/screens/InterestEditScreen";
import type { CategoryListData } from "../../src/features/interest/types/category";
import type {
    InterestReadResponse,
    InterestUpdateErrorResponse,
    InterestUpdateResponse,
} from "../../src/features/interest/types/interest";

jest.mock("@react-navigation/native", () => ({
  useNavigation: jest.fn(),
}));

jest.mock("../../src/app/providers/AuthProvider", () => ({
  useAuth: jest.fn(),
}));

jest.mock("../../src/features/interest/hooks/useCategories", () => ({
  useCategories: jest.fn(),
}));

jest.mock("../../src/features/interest/hooks/useUserInterests", () => ({
  useUserInterests: jest.fn(),
}));

jest.mock("../../src/features/interest/hooks/useUpdateInterests", () => ({
  useUpdateInterests: jest.fn(),
}));

jest.setTimeout(20_000);

const mockedUseNavigation = jest.mocked(useNavigation);

const mockedUseAuth = jest.mocked(useAuth);

const mockedUseCategories = jest.mocked(useCategories);

const mockedUseUserInterests = jest.mocked(useUserInterests);

const mockedUseUpdateInterests = jest.mocked(useUpdateInterests);

const goBackMock = jest.fn();

const revalidateSessionMock = jest.fn(async (): Promise<void> => undefined);

const completeInterestSelectionMock = jest.fn();

const refetchCategoriesMock = jest.fn();

const refetchUserInterestsMock = jest.fn();

const mutateMock = jest.fn();

const CATEGORY_DATA: CategoryListData = {
  categories: [
    {
      category_id: 1,
      category_code: "FASHION",
      category_name: "패션",
      parent_id: null,
      sort_order: 1,
      children: [],
    },
    {
      category_id: 2,
      category_code: "FOOD",
      category_name: "음식",
      parent_id: null,
      sort_order: 2,
      children: [],
    },
    {
      category_id: 3,
      category_code: "GAME",
      category_name: "게임",
      parent_id: null,
      sort_order: 3,
      children: [],
    },
  ],
};

const INITIAL_INTERESTS: InterestReadResponse = {
  selected_category_ids: [1],
  selected_count: 1,
};

const UPDATED_INTERESTS: InterestUpdateResponse = {
  selected_category_ids: [1, 2],
  selected_count: 2,
};

type MutationCallbacks = {
  onSuccess?: (data: InterestUpdateResponse) => void;

  onError?: (error: AxiosError<InterestUpdateErrorResponse>) => void;
};

function mockLoadedQueries(
  interestData: InterestReadResponse = INITIAL_INTERESTS,
): void {
  mockedUseCategories.mockReturnValue({
    data: CATEGORY_DATA,
    isError: false,
    isFetching: false,
    isPending: false,
    refetch: refetchCategoriesMock,
  } as unknown as ReturnType<typeof useCategories>);

  mockedUseUserInterests.mockReturnValue({
    data: interestData,
    isError: false,
    isFetching: false,
    isPending: false,
    refetch: refetchUserInterestsMock,
  } as unknown as ReturnType<typeof useUserInterests>);
}

function mockUpdateMutation(isPending = false): void {
  mockedUseUpdateInterests.mockReturnValue({
    mutate: mutateMock,
    isPending,
    isSuccess: false,
    error: null,
  } as unknown as ReturnType<typeof useUpdateInterests>);
}

function getMutationCallbacks(): MutationCallbacks {
  const call = mutateMock.mock.calls[0];

  if (!call) {
    throw new Error("관심사 수정 Mutation이 호출되지 않았습니다.");
  }

  return call[1] as MutationCallbacks;
}

function createUpdateError(
  statusCode: 400 | 401 | 404 | 409 | 422 | 500,
): AxiosError<InterestUpdateErrorResponse> {
  let data: unknown = null;

  if (statusCode === 400) {
    data = {
      inactive_category_ids: [2],
      child_category_ids: [],
    };
  }

  if (statusCode === 404) {
    data = {
      category_ids: [999],
    };
  }

  if (statusCode === 409) {
    data = {
      reason: "INTERESTS_NOT_INITIALIZED",
    };
  }

  return {
    isAxiosError: true,
    response: {
      status: statusCode,
      data: {
        success: false,
        statusCode,
        message: "테스트 오류",
        data,
      },
    },
  } as AxiosError<InterestUpdateErrorResponse>;
}

function createNetworkError(): AxiosError<InterestUpdateErrorResponse> {
  return {
    isAxiosError: true,
  } as AxiosError<InterestUpdateErrorResponse>;
}

async function renderLoadedScreen() {
  const rendered = await render(<InterestEditScreen />);

  await waitFor(() => {
    expect(
      screen.getByRole("button", {
        name: "패션",
      }).props.accessibilityState.selected,
    ).toBe(true);
  });

  return rendered;
}

async function editAndSubmit(): Promise<MutationCallbacks> {
  await renderLoadedScreen();

  await fireEvent.press(
    screen.getByRole("button", {
      name: "음식",
    }),
  );

  await fireEvent.press(
    screen.getByRole("button", {
      name: "변경사항 저장",
    }),
  );

  expect(mutateMock).toHaveBeenCalledWith(
    {
      category_ids: [1, 2],
    },
    expect.any(Object),
  );

  return getMutationCallbacks();
}

describe("InterestEditScreen", () => {
  let alertSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();

    alertSpy = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);

    mockedUseNavigation.mockReturnValue({
      goBack: goBackMock,
    } as unknown as ReturnType<typeof useNavigation>);

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
      establishSession: jest.fn(async (): Promise<void> => undefined),
      restoreSession: jest.fn(async (): Promise<void> => undefined),
      revalidateSession: revalidateSessionMock,
      completeInterestSelection: completeInterestSelectionMock,
      logout: jest.fn(async (): Promise<void> => undefined),
    } as ReturnType<typeof useAuth>);

    revalidateSessionMock.mockResolvedValue(undefined);

    mockLoadedQueries();
    mockUpdateMutation();
  });

  afterEach(() => {
    alertSpy.mockRestore();
  });

  test("기존 관심사를 Draft로 초기화하고 변경이 없으면 저장을 비활성화한다", async () => {
    await renderLoadedScreen();

    const saveButton = screen.getByRole("button", {
      name: "변경사항 저장",
    });

    expect(saveButton.props.accessibilityState.disabled).toBe(true);
  });

  test("선택을 변경하면 저장을 활성화하고 0개가 되면 다시 비활성화한다", async () => {
    await renderLoadedScreen();

    const saveButton = screen.getByRole("button", {
      name: "변경사항 저장",
    });

    await fireEvent.press(
      screen.getByRole("button", {
        name: "음식",
      }),
    );

    expect(saveButton.props.accessibilityState.disabled).toBe(false);

    await fireEvent.press(
      screen.getByRole("button", {
        name: "음식",
      }),
    );

    await fireEvent.press(
      screen.getByRole("button", {
        name: "패션",
      }),
    );

    expect(saveButton.props.accessibilityState.disabled).toBe(true);
  });

  test("Background Refetch가 편집 중 Draft를 덮어쓰지 않는다", async () => {
    const rendered = await renderLoadedScreen();

    await fireEvent.press(
      screen.getByRole("button", {
        name: "음식",
      }),
    );

    mockedUseUserInterests.mockReturnValue({
      data: {
        selected_category_ids: [1, 3],
        selected_count: 2,
      },
      isError: false,
      isFetching: false,
      isPending: false,
      refetch: refetchUserInterestsMock,
    } as unknown as ReturnType<typeof useUserInterests>);

    await rendered.rerender(<InterestEditScreen />);

    expect(
      screen.getByRole("button", {
        name: "음식",
      }).props.accessibilityState.selected,
    ).toBe(true);

    expect(
      screen.getByRole("button", {
        name: "게임",
      }).props.accessibilityState.selected,
    ).toBe(false);
  });

  test("PUT 성공 시 Draft를 성공 응답에 동기화하고 이전 화면으로 돌아간다", async () => {
    const callbacks = await editAndSubmit();

    await act(async () => {
      callbacks.onSuccess?.(UPDATED_INTERESTS);
    });

    expect(goBackMock).toHaveBeenCalledTimes(1);

    expect(completeInterestSelectionMock).not.toHaveBeenCalled();

    expect(revalidateSessionMock).not.toHaveBeenCalled();
  });

  test.each([400, 404] as const)(
    "PUT %i 오류 시 Category를 다시 조회하고 Draft를 유지한다",
    async (statusCode) => {
      const callbacks = await editAndSubmit();

      await act(async () => {
        callbacks.onError?.(createUpdateError(statusCode));
      });

      expect(refetchCategoriesMock).toHaveBeenCalledTimes(1);

      expect(
        screen.getByRole("button", {
          name: "음식",
        }).props.accessibilityState.selected,
      ).toBe(true);

      expect(goBackMock).not.toHaveBeenCalled();
    },
  );

  test("PUT 409 INTERESTS_NOT_INITIALIZED 시 Session을 재검증한다", async () => {
    const callbacks = await editAndSubmit();

    await act(async () => {
      callbacks.onError?.(createUpdateError(409));
    });

    await waitFor(() => {
      expect(revalidateSessionMock).toHaveBeenCalledTimes(1);
    });

    expect(goBackMock).not.toHaveBeenCalled();
  });

  test("PUT 401은 화면 자체 인증 Alert를 표시하지 않는다", async () => {
    const callbacks = await editAndSubmit();

    await act(async () => {
      callbacks.onError?.(createUpdateError(401));
    });

    expect(alertSpy).not.toHaveBeenCalled();

    expect(revalidateSessionMock).not.toHaveBeenCalled();

    expect(goBackMock).not.toHaveBeenCalled();
  });

  test("네트워크 오류 시 Draft를 유지한다", async () => {
    const callbacks = await editAndSubmit();

    await act(async () => {
      callbacks.onError?.(createNetworkError());
    });

    expect(alertSpy).toHaveBeenCalledWith("네트워크 오류", expect.any(String));

    expect(
      screen.getByRole("button", {
        name: "음식",
      }).props.accessibilityState.selected,
    ).toBe(true);
  });

  test.each([422, 500] as const)(
    "PUT %i 오류 시 Draft를 유지한다",
    async (statusCode) => {
      const callbacks = await editAndSubmit();

      await act(async () => {
        callbacks.onError?.(createUpdateError(statusCode));
      });

      expect(
        screen.getByRole("button", {
          name: "음식",
        }).props.accessibilityState.selected,
      ).toBe(true);

      expect(goBackMock).not.toHaveBeenCalled();
    },
  );

  test("관심사 Query가 초기 로딩 중이면 Loading 상태를 표시한다", async () => {
    mockedUseUserInterests.mockReturnValue({
      data: undefined,
      isError: false,
      isFetching: true,
      isPending: true,
      refetch: refetchUserInterestsMock,
    } as unknown as ReturnType<typeof useUserInterests>);

    await render(<InterestEditScreen />);

    expect(screen.getByRole("progressbar")).toBeTruthy();

    expect(
      screen.getByRole("button", {
        name: "변경사항 저장",
      }).props.accessibilityState.disabled,
    ).toBe(true);
  });
});
