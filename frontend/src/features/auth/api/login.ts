import { publicApiClient } from "../../../shared/api/publicApiClient";
import { CommonResponse } from "../../../shared/types/api";
import { LoginRequest, LoginResponse } from "../types/auth";

export async function login(
    request: LoginRequest,
): Promise<LoginResponse> {
    const response = await publicApiClient.post<
        CommonResponse<LoginResponse>
    >(
        "/auth/login",
        request,
    );

    return response.data.data;
}
