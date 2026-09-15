import { useQuery } from "@tanstack/react-query";

import { getCategories } from "../api/getCategories";
import {
  categoryQueryKeys,
} from "../queryKeys";

export function useCategories() {
  return useQuery({
    queryKey: categoryQueryKeys.all,
    queryFn: getCategories,
    staleTime: 1000 * 60 * 30,
    retry: 1,
  });
}
