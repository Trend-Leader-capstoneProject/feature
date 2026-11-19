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

import { assertAuthEpoch, getAuthEpoch } from "../../../shared/handler/authRequestGate";

export async function signup(
  request: SignupRequest,
): Promise<SignupResponse> {
  const epoch = getAuthEpoch();
  const response =
    await publicApiClient.post<
      CommonResponse<SignupResponse>
    >(
      "/auth/signup",
      request,
    );

  assertAuthEpoch(epoch);
  return { ...response.data.data, _requestEpoch: epoch };
}
