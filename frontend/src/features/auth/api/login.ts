import { publicApiClient } from "../../../shared/api/publicApiClient";
import type { CommonResponse } from "../../../shared/types/api";
import type { LoginRequest, LoginResponse } from "../types/auth";

import { assertAuthEpoch, getAuthEpoch } from "../../../shared/handler/authRequestGate";

export async function login(
    request: LoginRequest,
): Promise<LoginResponse> {
    const epoch = getAuthEpoch();
    const response = await publicApiClient.post<
        CommonResponse<LoginResponse>
    >(
        "/auth/login",
        request,
    );

    assertAuthEpoch(epoch);
    return { ...response.data.data, _requestEpoch: epoch };
}
