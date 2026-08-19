import { useMutation } from "@tanstack/react-query";

import { login } from "../api/login";
import type {
  LoginRequest,
  LoginResponse,
} from "../types/auth";

type LoginSuccessHandler = (
  result: LoginResponse,
) => Promise<void> | void;

export function useLogin(
  onSuccess?: LoginSuccessHandler,
) {
  return useMutation<
    LoginResponse,
    unknown,
    LoginRequest
  >({
    mutationFn: login,
    onSuccess,
    retry: 0,
  });
}
