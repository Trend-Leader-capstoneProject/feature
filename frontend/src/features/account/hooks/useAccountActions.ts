import { useMutation } from "@tanstack/react-query";
import { changePassword, verifyWithdrawal, withdraw } from "../api/accountApi";

export function useAccountActions() {
  const password = useMutation({
    mutationFn: (values: { current: string; next: string; confirm: string }) =>
      changePassword(values.current, values.next, values.confirm), retry: 0,
  });
  const verify = useMutation({ mutationFn: verifyWithdrawal, retry: 0 });
  const withdrawal = useMutation({ mutationFn: withdraw, retry: 0 });
  return { password, verify, withdrawal };
}
