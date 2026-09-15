import { useQuery } from "@tanstack/react-query";
import type { AxiosError } from "axios";

import { getUserInterests } from "../api/getUserInterests";
import type {
    InterestReadErrorResponse,
    InterestReadResponse,
} from "../types/interest";

export const userInterestQueryKeys = {
  all: ["user-interests"] as const,
  me: ["user-interests", "me"] as const,
};

export function useUserInterests() {
  return useQuery<
    InterestReadResponse,
    AxiosError<InterestReadErrorResponse>
  >({
    queryKey: userInterestQueryKeys.me,
    queryFn: getUserInterests,
    staleTime: 0,
    retry: (failureCount, error) => {
      if (error.response?.status === 401) {
        return false;
      }

      return failureCount < 1;
    },
  });
}
