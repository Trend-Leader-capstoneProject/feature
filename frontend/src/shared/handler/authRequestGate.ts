let authenticatedRequestsBlocked = false;
let authEpoch = 0;
export class StaleAuthOperationError extends Error {
  constructor() { super("종료되었거나 변경된 로그인 작업입니다."); }
}
export function blockAuthenticatedRequests(): void { authenticatedRequestsBlocked = true; }
export function allowAuthenticatedRequests(): void { authenticatedRequestsBlocked = false; }
export function areAuthenticatedRequestsBlocked(): boolean { return authenticatedRequestsBlocked; }
export function getAuthEpoch(): number { return authEpoch; }
export function advanceAuthEpoch(): number {
  blockAuthenticatedRequests();
  return ++authEpoch;
}
export function assertAuthEpoch(epoch: number): void {
  if (epoch !== authEpoch) throw new StaleAuthOperationError();
}
export function assertActiveAuthEpoch(epoch: number): void {
  assertAuthEpoch(epoch);
  if (authenticatedRequestsBlocked) throw new StaleAuthOperationError();
}
