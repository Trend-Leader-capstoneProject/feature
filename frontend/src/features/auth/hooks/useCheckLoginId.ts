import {
    useMutation,
} from "@tanstack/react-query";
import type {
    AxiosError,
} from "axios";

import {
    checkLoginId,
} from "../api/checkLoginId";
import type {
    CheckLoginIdErrorResponse,
    CheckLoginIdRequest,
    CheckLoginIdResponse,
} from "../types/auth";

export function useCheckLoginId() {
  return useMutation<
    CheckLoginIdResponse,
    AxiosError<CheckLoginIdErrorResponse>,
    CheckLoginIdRequest
  >({
    mutationFn: checkLoginId,
    retry: 0,
  });
}
