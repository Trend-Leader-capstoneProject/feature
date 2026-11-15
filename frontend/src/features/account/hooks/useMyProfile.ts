import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../../app/providers/AuthProvider";
import { getAuthEpoch } from "../../../shared/handler/authRequestGate";
import { getProfile } from "../api/accountApi";

export function profileKey(userId: number | undefined, epoch = getAuthEpoch()) {
  return ["my-profile", epoch, userId] as const;
}
export function useMyProfile() {
  const { authState } = useAuth();
  const userId = authState.status === "AUTHENTICATED" ? authState.session.user.user_id : undefined;
  return useQuery({
    queryKey: profileKey(userId), queryFn: getProfile,
    enabled: userId !== undefined, retry: false,
  });
}
