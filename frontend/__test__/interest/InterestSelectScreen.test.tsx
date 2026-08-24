import {
    fireEvent,
    render,
    screen,
    waitFor
} from "@testing-library/react-native";
import type {
    AxiosError,
} from "axios";
import {
    Alert,
} from "react-native";

import {
    useAuth,
} from "../../src/app/providers/AuthProvider";
import {
    useCategories,
} from "../../src/features/interest/hooks/useCategories";
import {
    useSaveInterests,
} from "../../src/features/interest/hooks/useSaveInterests";
import {
    InterestSelectScreen,
} from "../../src/features/interest/screens/InterestSelectScreen";
import type {
    CategoryListData,
} from "../../src/features/interest/types/category";
import type {
    InterestSaveErrorResponse,
} from "../../src/features/interest/types/interest";

jest.mock(
  "../../src/app/providers/AuthProvider",
  () => ({
    useAuth: jest.fn(),
  }),
);

jest.mock(
  "../../src/features/interest/hooks/useCategories",
  () => ({
    useCategories: jest.fn(),
  }),
);

jest.mock(
  "../../src/features/interest/hooks/useSaveInterests",
  () => ({
    useSaveInterests: jest.fn(),
  }),
);

const mockedUseAuth =
  jest.mocked(useAuth);

const mockedUseCategories =
  jest.mocked(useCategories);

const mockedUseSaveInterests =
  jest.mocked(useSaveInterests);

const completeInterestSelectionMock =
  jest.fn();

const revalidateSessionMock =
  jest.fn(async (): Promise<void> => undefined);

const mutateMock =
  jest.fn();

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
  ],
};

type MutationCallbacks = {
  onSuccess?: () => void;
  onError?: (
    error: AxiosError<InterestSaveErrorResponse>,
  ) => void;
};

function createInterestSaveError(
  statusCode: 401 | 409,
): AxiosError<InterestSaveErrorResponse> {
  return {
    isAxiosError: true,
    response: {
      data: {
        success: false,
        statusCode,
        message: "테스트 오류",
        data: null,
      },
    },
  } as AxiosError<InterestSaveErrorResponse>;
}

function getMutationCallbacks(): MutationCallbacks {
  const call =
    mutateMock.mock.calls[0];

  if (!call) {
    throw new Error(
      "관심사 저장 Mutation이 호출되지 않았습니다.",
    );
  }

  return call[1] as MutationCallbacks;
}

async function submitInterestSelection(): Promise<
  MutationCallbacks
> {
  await render(
    <InterestSelectScreen />,
  );

  await fireEvent.press(
    screen.getByRole(
      "button",
      {
        name: "패션",
      },
    ),
  );

  await fireEvent.press(
    screen.getByRole(
      "button",
      {
        name: "선택 완료",
      },
    ),
  );

  expect(
    mutateMock,
  ).toHaveBeenCalledWith(
    {
      category_ids: [1],
    },
    expect.any(Object),
  );

  return getMutationCallbacks();
}

describe(
  "InterestSelectScreen auth session integration",
  () => {
    let alertSpy:
      jest.SpyInstance;

    beforeEach(() => {
      jest.clearAllMocks();

      revalidateSessionMock
        .mockResolvedValue(undefined);

      alertSpy =
        jest.spyOn(
          Alert,
          "alert",
        ).mockImplementation(
          () => undefined,
        );

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
            has_selected_interests: false,
            next_step: "INTEREST_SELECTION",
          },
        },
        establishSession:
          jest.fn(
            async (): Promise<void> =>
              undefined,
          ),
        restoreSession:
          jest.fn(
            async (): Promise<void> =>
              undefined,
          ),
        revalidateSession:
          revalidateSessionMock,
        completeInterestSelection:
          completeInterestSelectionMock,
        logout:
          jest.fn(
            async (): Promise<void> =>
              undefined,
          ),
      } as ReturnType<typeof useAuth>);

      mockedUseCategories.mockReturnValue({
        data: CATEGORY_DATA,
        isError: false,
        isFetching: false,
        isPending: false,
        refetch: jest.fn(),
      } as unknown as ReturnType<
        typeof useCategories
      >);

      mockedUseSaveInterests.mockReturnValue({
        mutate: mutateMock,
        error: null,
        isPending: false,
        isSuccess: false,
      } as unknown as ReturnType<
        typeof useSaveInterests
      >);
    });

    afterEach(() => {
      alertSpy.mockRestore();
    });

    test(
        "관심사 저장 201 성공 시 completeInterestSelection을 호출한다",
        async () => {
            const callbacks =
            await submitInterestSelection();

            callbacks.onSuccess?.();

            expect(
            completeInterestSelectionMock,
            ).toHaveBeenCalledTimes(1);

            expect(
            revalidateSessionMock,
            ).not.toHaveBeenCalled();
        },
        );

    test(
        "관심사 저장 409 발생 시 Session을 재검증한다",
        async () => {
            const callbacks =
            await submitInterestSelection();

            callbacks.onError?.(
            createInterestSaveError(409),
            );

            await waitFor(() => {
            expect(
                revalidateSessionMock,
            ).toHaveBeenCalledTimes(1);
            });

            expect(
            completeInterestSelectionMock,
            ).not.toHaveBeenCalled();
        },
        );

    test(
        "관심사 저장 401은 화면 자체의 인증 Alert를 표시하지 않는다",
        async () => {
            const callbacks =
            await submitInterestSelection();

            callbacks.onError?.(
            createInterestSaveError(401),
            );

            expect(
            alertSpy,
            ).not.toHaveBeenCalled();

            expect(
            completeInterestSelectionMock,
            ).not.toHaveBeenCalled();

            expect(
            revalidateSessionMock,
            ).not.toHaveBeenCalled();
        },
    );
  },
);
