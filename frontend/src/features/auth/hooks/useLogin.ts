import { useMutation } from "@tanstack/react-query";

import { saveAccessToken } from "../../../shared/storage/tokenStorage";
import { login } from "../api/login";
import type { LoginRequest, LoginResponse } from "../types/auth";

async function loginAndSaveAccessToken(
  request: LoginRequest,
): Promise<LoginResponse> {
  const result = await login(
    request,
  );

  await saveAccessToken(
    result.access_token,
  );

  return result;
}

export function useLogin() {
    return useMutation<
        LoginResponse,
        unknown,
        LoginRequest
    >({
        mutationFn: loginAndSaveAccessToken,
        retry: 0,
    });
}
