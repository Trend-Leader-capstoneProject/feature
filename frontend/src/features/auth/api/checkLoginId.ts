import {
    publicApiClient,
} from "../../../shared/api/publicApiClient";
import type {
    CommonResponse,
} from "../../../shared/types/api";
import type {
    CheckLoginIdRequest,
    CheckLoginIdResponse,
} from "../types/auth";

export async function checkLoginId(
  request: CheckLoginIdRequest,
): Promise<CheckLoginIdResponse> {
  const response =
    await publicApiClient.get<
      CommonResponse<CheckLoginIdResponse>
    >(
      "/auth/check-login-id",
      {
        params: request,
      },
    );

  return response.data.data;
}
