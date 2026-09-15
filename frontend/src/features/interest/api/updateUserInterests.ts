import { authenticatedApiClient } from "../../../shared/api/authenticatedApiClient";
import { CommonResponse } from "../../../shared/types/api";
import {
    InterestUpdateRequest,
    InterestUpdateResponse,
} from "../types/interest";

export async function updateUserInterests(
  request: InterestUpdateRequest,
): Promise<InterestUpdateResponse> {
  const response =
    await authenticatedApiClient.put<
      CommonResponse<InterestUpdateResponse>
    >(
      "/users/me/interests",
      request,
    );

  return response.data.data;
}
