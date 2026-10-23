import {
    authenticatedApiClient,
} from "../../../shared/api/authenticatedApiClient";

import type {
    CommonResponse,
} from "../../../shared/types/api";

import type {
    GetPersonalizedTrendsParams,
    TrendListData,
} from "../types/trend";


export async function getPersonalizedTrends(
  params: GetPersonalizedTrendsParams = {},
  signal?: AbortSignal,
): Promise<TrendListData> {
  const response =
    await authenticatedApiClient.get<
      CommonResponse<TrendListData>
    >(
      "/trends/personalized",
      {
        params,
        signal,
      },
    );

  return response.data.data;
}
