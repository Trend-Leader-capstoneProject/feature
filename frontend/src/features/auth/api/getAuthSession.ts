import { authenticatedApiClient } from "../../../shared/api/authenticatedApiClient";
import { CommonResponse } from "../../../shared/types/api";
import { SessionResponse } from "../types/auth";

export async function getAuthSession(): Promise<SessionResponse> {
    const response =
        await authenticatedApiClient.get<
            CommonResponse<SessionResponse>
        >(
            "/auth/session",
        );

    return response.data.data;
}
