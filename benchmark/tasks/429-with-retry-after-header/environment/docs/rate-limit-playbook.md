The batch worker used to cap any single wait at 2 seconds so one tenant could not monopolize a worker.

That safeguard is no longer valid for this integration. The provider's `Retry-After` header is now authoritative, and different cases can return different wait windows.
