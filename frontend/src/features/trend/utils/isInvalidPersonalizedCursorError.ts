import {
    isAxiosError,
} from "axios";

import type {
    CommonErrorResponse,
} from "../../../shared/types/api";

import type {
    TrendListErrorData,
} from "../types/trend";

export function isInvalidPersonalizedCursorError(
  error: unknown,
): boolean {
  if (
    !isAxiosError<
      CommonErrorResponse<TrendListErrorData, 400>
    >(error)
  ) {
    return false;
  }

  return (
    error.response?.status === 400 &&
    error.response.data?.data?.reason ===
      "INVALID_CURSOR"
  );
}
