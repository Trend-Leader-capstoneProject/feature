import {
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import type { AxiosError } from "axios";

import { updateUserInterests } from "../api/updateUserInterests";
import {
  userInterestQueryKeys,
} from "../queryKeys";
import type {
  InterestUpdateErrorResponse,
  InterestUpdateRequest,
  InterestUpdateResponse,
} from "../types/interest";

export function useUpdateInterests() {
  const queryClient =
    useQueryClient();

  return useMutation<
    InterestUpdateResponse,
    AxiosError<InterestUpdateErrorResponse>,
    InterestUpdateRequest
  >({
    mutationFn: updateUserInterests,
    retry: 0,

    onSuccess: (data) => {
      queryClient.setQueryData(
        userInterestQueryKeys.me,
        data,
      );
    },
  });
}
