import { useMutation } from "@tanstack/react-query";
import type { AxiosError } from "axios";

import { saveUserInterests } from "../api/saveUserInterests";
import type {
    InterestSaveErrorResponse,
    InterestSaveRequest,
    InterestSaveResponse,
} from "../types/interest";

export function useSaveInterests() {
  return useMutation<
    InterestSaveResponse,
    AxiosError<InterestSaveErrorResponse>,
    InterestSaveRequest
  >({
    mutationFn: saveUserInterests,
    retry: 0,
  });
}