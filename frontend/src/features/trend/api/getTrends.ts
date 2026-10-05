import { publicApiClient } from "../../../shared/api/publicApiClient";
import type { CommonResponse } from "../../../shared/types/api";
import type {
    GetTrendsParams,
    TrendListData,
} from "../types/trend";


export async function getTrends(
  params: GetTrendsParams = {},
): Promise<TrendListData> {
  const response =
    await publicApiClient.get<
      CommonResponse<TrendListData>
    >(
      "/trends",
      {
        params,
      },
    );

  return response.data.data;
}
