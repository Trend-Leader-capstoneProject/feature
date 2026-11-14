import { blockAuthenticatedRequests } from "./authRequestGate";
let handler: (() => void) | null = null;
export function registerAuthStorageFailureHandler(next: () => void): () => void {
  handler = next;
  return () => { if (handler === next) handler = null; };
}
export function notifyAuthStorageFailure(): void {
  blockAuthenticatedRequests();
  handler?.();
}
