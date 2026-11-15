import { useCallback } from "react";
import { BackHandler } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { useNavigationTransitionGuard, type TransitionNavigation } from "./useNavigationTransitionGuard";

export type ReturnNavigation = TransitionNavigation;

export function useScreenReturn(navigation: ReturnNavigation) {
  const { run, disabled } = useNavigationTransitionGuard(navigation);
  const goBack = useCallback(() => run(() => navigation.goBack()), [navigation, run]);

  useFocusEffect(useCallback(() => {
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => {
      goBack();
      return true;
    });
    return () => subscription.remove();
  }, [goBack]));

  return { goBack, disabled };
}
