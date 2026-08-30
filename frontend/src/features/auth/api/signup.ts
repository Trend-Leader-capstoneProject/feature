import {
    publicApiClient,
} from "../../../shared/api/publicApiClient";
import type {
    CommonResponse,
} from "../../../shared/types/api";
import type {
    SignupRequest,
    SignupResponse,
} from "../types/auth";

export async function signup(
  request: SignupRequest,
): Promise<SignupResponse> {
  const response =
    await publicApiClient.post<
      CommonResponse<SignupResponse>
    >(
      "/auth/signup",
      request,
    );

  return response.data.data;
}
