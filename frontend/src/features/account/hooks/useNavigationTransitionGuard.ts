import { useCallback, useEffect, useRef, useState } from "react";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { AppStackParamList } from "../../../app/navigation/AppNavigator";

export type TransitionNavigation = Pick<
  NativeStackNavigationProp<AppStackParamList>,
  "addListener" | "goBack" | "isFocused"
>;

// JS의 focus만으로는 native 애니메이션 완료를 알 수 없다.
export function useNavigationTransitionGuard(navigation: TransitionNavigation) {
  const transitioning = useRef(true);
  const dispatched = useRef(false);
  const [disabled, setDisabled] = useState(true);

  useEffect(() => {
    const removeFocus = navigation.addListener("focus", () => {
      transitioning.current = true;
      dispatched.current = false;
      setDisabled(true);
    });
    const removeStart = navigation.addListener("transitionStart", () => {
      transitioning.current = true;
      setDisabled(true);
    });
    const removeEnd = navigation.addListener("transitionEnd", event => {
      if (!event.data.closing && !dispatched.current && navigation.isFocused()) {
        transitioning.current = false;
        setDisabled(false);
      }
    });
    return () => { removeFocus(); removeStart(); removeEnd(); };
  }, [navigation]);

  const run = useCallback((action: () => void) => {
    if (transitioning.current || dispatched.current || !navigation.isFocused()) return;
    dispatched.current = true;
    setDisabled(true);
    action();
  }, [navigation]);

  return { run, disabled };
}
