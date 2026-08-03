import { env } from "../../app/config/env";

interface ErrorResponse {
    success?: false;
    statusCode?: number;
    message?: string;
    data?: unknown;
}

export async function apiRequest<ResponseData>(
    path: string,
    init?: RequestInit,
): Promise<ResponseData> {
    const response = await fetch(`${env.apiBaseUrl}${path}`, {
        ...init,
        headers: {
            Accept: "application/json",
            ...init?.headers,
        },
    });

    const responseBody = (await response
        .json()
        .catch(() => null)) as ErrorResponse | ResponseData | null;
    
    if (!response.ok) {
        const ErrorResponse = responseBody as ErrorResponse | null;
        
        throw new Error(
            ErrorResponse?.message ??
                `API 요청에 실패했습니다. status=${response.status}` ,
        );
    }


    if (responseBody === null) {
        throw new Error("API 응답 Body가 비어 있습니다.")
    }

    return responseBody as ResponseData;
}