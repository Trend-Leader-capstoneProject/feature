export type AuthFailureHandler =
  () => Promise<void>;

let authFailureHandler:
  AuthFailureHandler | null = null;

export function registerAuthFailureHandler(
  handler: AuthFailureHandler,
): () => void {
  authFailureHandler = handler;

  return () => {
    if (authFailureHandler === handler) {
      authFailureHandler = null;
    }
  };
}

export function notifyAuthFailure(): void {
  const handler = authFailureHandler;

  if (!handler) {
    return;
  }

  void handler().catch(() => undefined);
}
