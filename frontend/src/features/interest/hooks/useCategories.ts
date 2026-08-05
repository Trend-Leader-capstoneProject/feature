import { useQuery } from "@tanstack/react-query";

import { getCategories } from "../api/getCategories";

export const categoryQueryKeys = {
  all: ["categories"] as const,
};


export function useCategories() {
    return useQuery({
        queryKey: categoryQueryKeys.all,
        queryFn: getCategories,
        staleTime: 1000 * 60 * 30,
        retry: 1,
    });
}