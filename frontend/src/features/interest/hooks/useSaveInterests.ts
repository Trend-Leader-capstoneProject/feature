import { useMutation } from "@tanstack/react-query";
import { saveUserInterests } from "../api/saveUserInterests";

export function useSaveInterests() {
    return useMutation({
        mutationFn: saveUserInterests,
        retry: 0,
    });
}