import { authenticatedApiClient } from "../../../shared/api/authenticatedApiClient";
import { CommonResponse } from "../../../shared/types/api";
import { InterestSaveRequest, InterestSaveResponse } from "../types/interest";

export async function saveUserInterests(
    request: InterestSaveRequest,
): Promise<InterestSaveResponse> {
    const response = await authenticatedApiClient.post<
      CommonResponse<InterestSaveResponse>
      >(
        "/users/me/interests",
        request,
      );
    return response.data.data;
}
