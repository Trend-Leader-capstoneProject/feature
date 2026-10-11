import type { AxiosError } from "axios";

import {
    isInvalidPersonalizedCursorError,
} from "../../src/features/trend/utils/isInvalidPersonalizedCursorError";

function createMockError(
  status: number,
  reason?: string,
): AxiosError {
  return {
    isAxiosError: true,
    response: {
      status,
      data: {
        success: false,
        statusCode: status,
        message: "요청 오류",
        data: reason
          ? { reason }
          : null,
      },
    },
  } as AxiosError;
}

describe("isInvalidPersonalizedCursorError", () => {
  test("400 INVALID_CURSOR 오류를 식별한다", () => {
    const error = createMockError(
      400,
      "INVALID_CURSOR",
    );

    expect(
      isInvalidPersonalizedCursorError(error),
    ).toBe(true);
  });

  test("400이더라도 다른 오류라면 복구 대상으로 판단하지 않는다", () => {
    const error = createMockError(
      400,
      "OTHER_ERROR",
    );

    expect(
      isInvalidPersonalizedCursorError(error),
    ).toBe(false);
  });

  test("409 도메인 오류는 복구 대상이 아니다", () => {
    const error = createMockError(
      409,
      "INTERESTS_NOT_AVAILABLE",
    );

    expect(
      isInvalidPersonalizedCursorError(error),
    ).toBe(false);
  });

  test("HTTP 401 오류는 복구 대상이 아니다", () => {
    const error = createMockError(401);

    expect(
      isInvalidPersonalizedCursorError(error),
    ).toBe(false);
  });

  test("일반 Error와 네트워크 오류는 복구 대상이 아니다", () => {
    expect(
      isInvalidPersonalizedCursorError(
        new Error("Network Error"),
      ),
    ).toBe(false);

    expect(
      isInvalidPersonalizedCursorError(
        createMockError(400),
      ),
    ).toBe(false);
  });
});
