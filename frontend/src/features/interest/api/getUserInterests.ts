import { authenticatedApiClient } from "../../../shared/api/authenticatedApiClient";
import { CommonResponse } from "../../../shared/types/api";
import { InterestReadResponse } from "../types/interest";

export async function getUserInterests(): Promise<InterestReadResponse> {
  const response =
    await authenticatedApiClient.get<
      CommonResponse<InterestReadResponse>
    >(
        "/users/me/interests",
    );

  return response.data.data;
}
