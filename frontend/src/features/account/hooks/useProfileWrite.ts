import axios from "axios";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../../app/providers/AuthProvider";
import { assertActiveAuthEpoch, getAuthEpoch, StaleAuthOperationError } from "../../../shared/handler/authRequestGate";
import { getErrorReason } from "../../../shared/api/authenticatedApiClient";
import { getProfile } from "../api/accountApi";
import { profileKey } from "./useMyProfile";
import type { Profile } from "../types/account";

export function useProfileWrite() {
  const queryClient = useQueryClient();
  const { authState } = useAuth();
  const userId = authState.status === "AUTHENTICATED" ? authState.session.user.user_id : undefined;
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [verified, setVerified] = useState(false);
  const busy = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const mutation = useMutation({ mutationFn: (operation: () => Promise<Profile>) => operation(), retry: 0 });
  async function verify(epoch = getAuthEpoch()) {
    try {
      const result = await getProfile();
      assertActiveAuthEpoch(epoch);
      queryClient.setQueryData(profileKey(userId, epoch), result);
      if (mounted.current) {
        setVerified(true);
        setMessage("저장 결과를 확인하지 못했습니다. 현재 서버 정보를 확인해 주세요.");
      }
    } catch (error) {
      if (error instanceof StaleAuthOperationError || epoch !== getAuthEpoch()) return;
      if (mounted.current) {
        setVerified(false);
        setMessage("저장 결과와 현재 정보를 확인하지 못했습니다. 확인을 다시 시도해 주세요.");
      }
    }
  }
  async function run(operation: () => Promise<Profile>): Promise<"SUCCESS" | "FAILED" | "UNKNOWN"> {
    if (busy.current) return "FAILED";
    busy.current = true;
    const epoch = getAuthEpoch();
    setPending(true); setMessage("");
    try {
      const result = await mutation.mutateAsync(operation);
      assertActiveAuthEpoch(epoch);
      queryClient.setQueryData(profileKey(userId, epoch), result);
      return "SUCCESS";
    } catch (error) {
      if (error instanceof StaleAuthOperationError || epoch !== getAuthEpoch()) return "FAILED";
      const reason = getErrorReason(error);
      if (axios.isAxiosError(error) && error.response &&
        (error.response.status < 500 || reason === "PROFILE_IMAGE_PROCESSING_BUSY")) {
        const messages: Record<string, string> = {
          DUPLICATED_NICKNAME: "이미 사용 중인 닉네임입니다. 중복 확인을 다시 해 주세요.",
          PROFILE_IMAGE_TOO_LARGE: "사진은 5MB 이하로 선택해 주세요.",
          PROFILE_IMAGE_PIXEL_LIMIT_EXCEEDED: "사진은 2,000만 화소 이하여야 합니다.",
          PROFILE_IMAGE_UNSUPPORTED: "정지 JPEG·PNG 사진을 선택해 주세요.",
          PROFILE_IMAGE_INVALID: "사진을 읽을 수 없습니다. 다른 사진을 선택해 주세요.",
          PROFILE_IMAGE_PROCESSING_BUSY: "사진 처리 중입니다. 잠시 후 다시 시도해 주세요.",
        };
        if (mounted.current) setMessage(messages[reason ?? ""] ?? "입력을 확인하고 다시 시도해 주세요.");
        return "FAILED";
      }
      setUncertain(true);
      setVerified(false);
      await verify(epoch); // 자동 재저장 없이 논리 조회 한 번만 수행한다.
      return "UNKNOWN";
    } finally {
      busy.current = false;
      if (mounted.current && epoch === getAuthEpoch()) setPending(false);
    }
  }
  async function checkResult() {
    if (busy.current) return;
    busy.current = true; setPending(true);
    try { await verify(); } finally { busy.current = false; if (mounted.current) setPending(false); }
  }
  return { pending, busy, message, uncertain, verified, run, checkResult };
}
