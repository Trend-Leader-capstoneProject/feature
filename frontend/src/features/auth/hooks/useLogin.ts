import { useMutation } from "@tanstack/react-query";
import type { AxiosError } from "axios";

import { login } from "../api/login";
import type { LoginErrorResponse, LoginRequest, LoginResponse } from "../types/auth";

export function useLogin() {
    return useMutation<
        LoginResponse,
        AxiosError<LoginErrorResponse>,
        LoginRequest
    >({
        mutationFn: login,
        retry: 0,
    });
}