let authenticatedRequestsBlocked = false;

export function blockAuthenticatedRequests(): void {
  authenticatedRequestsBlocked = true;
}

export function allowAuthenticatedRequests(): void {
  authenticatedRequestsBlocked = false;
}

export function areAuthenticatedRequestsBlocked(): boolean {
  return authenticatedRequestsBlocked;
}
