import type {
    CommonErrorResponse,
    ValidationErrorData,
} from "../../../shared/types/api";

export type UserStatus =
  | "ACTIVE"
  | "WITHDRAWN"
  | "SUSPENDED";

export type AuthNextStep =
  | "MAIN"
  | "INTEREST_SELECTION";

export interface AuthUser {
  user_id: number;
  login_id: string;
  name: string;
  status: UserStatus;
}

export interface LoginRequest {
  login_id: string;
  password: string;
}

export interface SessionResponse {
  user: AuthUser;
  has_selected_interests: boolean;
  next_step: AuthNextStep;
}

export interface LoginResponse
  extends SessionResponse {
  access_token: string;
  token_type: "Bearer";
}

export type LoginErrorResponse =
  | CommonErrorResponse<null, 401>
  | CommonErrorResponse<
      ValidationErrorData,
      422
    >
  | CommonErrorResponse<null, 500>;
