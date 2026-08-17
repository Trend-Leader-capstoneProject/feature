import { apiClient } from "../../../shared/api/apiClient";
import { CommonResponse } from "../../../shared/types/api";
import { LoginRequest, LoginResponse } from "../types/auth";

export async function login(
    request: LoginRequest,
): Promise<LoginResponse> {
    const response = await apiClient.post<
        CommonResponse<LoginResponse>
    >(
        "/auth/login",
        request,
    );

    return response.data.data;
}
