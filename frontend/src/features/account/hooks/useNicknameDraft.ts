import { useRef, useState } from "react";
import { checkNickname } from "../api/accountApi";
import { getAuthEpoch } from "../../../shared/handler/authRequestGate";

export function normalizeNickname(raw: string): string {
  const value = raw.trim().normalize("NFC");
  if (!/^[가-힣A-Za-z0-9_]{2,10}$/.test(value)) throw new Error("닉네임은 2~10자 한글·영문·숫자·밑줄만 사용할 수 있습니다.");
  return value;
}
export function useNicknameDraft(initial = "", own = false) {
  const [value, setValue] = useState(initial);
  const [available, setAvailable] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [checking, setChecking] = useState(false);
  const generation = useRef(0);
  const current = useRef(initial);
  function update(next: string) {
    current.current = next;
    generation.current++;
    setValue(next); setAvailable(null); setFeedback(""); setChecking(false);
  }
  function invalidate(message: string) {
    generation.current++; setAvailable(null); setFeedback(message); setChecking(false);
  }
  async function check() {
    const request = ++generation.current;
    const epoch = getAuthEpoch();
    let candidate: string;
    try { candidate = normalizeNickname(current.current); }
    catch (error) { setFeedback((error as Error).message); return; }
    setChecking(true);
    try {
      const result = await checkNickname(candidate, own);
      if (request !== generation.current || epoch !== getAuthEpoch()) return;
      setAvailable(result.is_available ? candidate : null);
      setFeedback(result.is_available ? "사용 가능한 닉네임입니다." : "이미 사용 중인 닉네임입니다.");
    } catch {
      if (request === generation.current && epoch === getAuthEpoch()) setFeedback("중복 확인에 실패했습니다. 다시 시도해 주세요.");
    } finally {
      if (request === generation.current) setChecking(false);
    }
  }
  return { value, available, feedback, checking, update, invalidate, check };
}
