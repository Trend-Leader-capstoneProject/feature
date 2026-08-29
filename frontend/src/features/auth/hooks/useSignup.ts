import { useMutation } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { signup } from "../api/signup";
import { SignupErrorResponse, SignupRequest, SignupResponse } from "../types/auth";

type SignupSuccessHandler = (
  result: SignupResponse,
) => Promise<void> | void;

export function useSignup(
  onSuccess?: SignupSuccessHandler,
) {
    return useMutation<
      SignupResponse,
      AxiosError<SignupErrorResponse>,
      SignupRequest
    >({
        mutationFn: signup,
        onSuccess,
        retry: 0,
    })
}
