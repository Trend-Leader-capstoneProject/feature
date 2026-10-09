import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { AxiosError } from "axios";

import { trendQueryKeys } from "../../trend/queryKeys";
import { updateUserInterests } from "../api/updateUserInterests";
import { userInterestQueryKeys } from "../queryKeys";
import type {
  InterestUpdateErrorResponse,
  InterestUpdateRequest,
  InterestUpdateResponse,
} from "../types/interest";

export function useUpdateInterests() {
  const queryClient = useQueryClient();

  return useMutation<
    InterestUpdateResponse,
    AxiosError<InterestUpdateErrorResponse>,
    InterestUpdateRequest
  >({
    mutationFn: updateUserInterests,
    retry: 0,

    onSuccess: async (data) => {
      // 1. 서버가 반환한 최종 관심사 상태 반영
      queryClient.setQueryData(userInterestQueryKeys.me, data);

      // 2. 이전 관심사 기준 Personalized 요청 취소
      await queryClient.cancelQueries({
        queryKey: trendQueryKeys.personalizedAll,
      });

      // 3. 이전 Pages 및 Cursor 제거
      queryClient.removeQueries({
        queryKey: trendQueryKeys.personalizedAll,
      });
    },
  });
}
