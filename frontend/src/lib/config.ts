/**
 * Upload limit used for client-side checks. Matches the backend default (MAX_UPLOAD_MB=10);
 * the server enforces its own setting either way.
 */
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
