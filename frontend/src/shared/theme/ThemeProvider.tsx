import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type PropsWithChildren } from "react";
import { Appearance, useColorScheme } from "react-native";
import * as SecureStore from "expo-secure-store";
import { colors, darkColors, type ThemeColors } from "../constants/colors";

export type ThemePreference = "SYSTEM" | "LIGHT" | "DARK";
export const THEME_STORAGE_KEY = "trend-leader.theme.v1";
type ThemeContextValue = {
  preference: ThemePreference;
  scheme: "light" | "dark";
  colors: ThemeColors;
  ready: boolean;
  saving: boolean;
  error: string | null;
  setPreference: (value: ThemePreference) => Promise<void>;
  retryRestore: () => void;
};
const ThemeContext = createContext<ThemeContextValue>({
  preference: "SYSTEM", scheme: "light", colors, ready: true, saving: false, error: null,
  setPreference: async () => undefined, retryRestore: () => undefined,
});
function isPreference(value: unknown): value is ThemePreference {
  return value === "SYSTEM" || value === "LIGHT" || value === "DARK";
}
export function ThemeProvider({ children }: PropsWithChildren) {
  const deviceScheme = useColorScheme();
  const [preference, setValue] = useState<ThemePreference>("SYSTEM");
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const busy = useRef(false);
  const revision = useRef(0);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    let active = true;
    const startedAt = revision.current;
    setReady(false);
    void SecureStore.getItemAsync(THEME_STORAGE_KEY).then(value => {
      if (!active || revision.current !== startedAt) return;
      // Unknown values from another version fall back to the device setting.
      setValue(isPreference(value) ? value : "SYSTEM");
      setError(null);
    }).catch(() => {
      if (active && revision.current === startedAt) setError("테마 설정을 불러오지 못했습니다. 다시 시도해 주세요.");
    }).finally(() => { if (active) setReady(true); });
    return () => { active = false; };
  }, [attempt]);
  useEffect(() => {
    Appearance.setColorScheme(preference === "SYSTEM" ? "unspecified" : preference === "DARK" ? "dark" : "light");
  }, [preference]);
  const setPreference = useCallback(async (value: ThemePreference) => {
    if (!isPreference(value) || busy.current) return;
    busy.current = true;
    revision.current += 1;
    setSaving(true);
    setError(null);
    try {
      await SecureStore.setItemAsync(THEME_STORAGE_KEY, value);
      if (mounted.current) setValue(value);
    } catch {
      if (mounted.current) setError("테마 설정을 저장하지 못했습니다. 다시 선택해 주세요.");
    } finally {
      busy.current = false;
      if (mounted.current) setSaving(false);
    }
  }, []);
  const retryRestore = useCallback(() => { if (!busy.current) setAttempt(value => value + 1); }, []);
  const scheme = preference === "SYSTEM" ? (deviceScheme === "dark" ? "dark" : "light") : preference === "DARK" ? "dark" : "light";
  const value = useMemo<ThemeContextValue>(() => ({
    preference, scheme, colors: scheme === "dark" ? darkColors : colors, ready, saving, error,
    setPreference, retryRestore,
  }), [preference, scheme, ready, saving, error, setPreference, retryRestore]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
export function useAppTheme() { return useContext(ThemeContext); }
