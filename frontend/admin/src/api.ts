import type {
  AdminAccount,
  AdminStats,
  AdminUser,
  AppSettings,
  AuditEntry,
  BroadcastProgress,
  Car,
  Lead,
  Page,
  User,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const API_ROOT = `${API_BASE}/api/v1`;
let refreshRequest: Promise<boolean> | null = null;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
  retryAfterRefresh = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  if (
    response.status === 401
    && retryAfterRefresh
    && !path.startsWith("/auth/admin/login")
    && !path.startsWith("/auth/admin/refresh")
    && !path.startsWith("/auth/admin/logout")
  ) {
    if (!refreshRequest) {
      refreshRequest = fetch(`${API_ROOT}/auth/admin/refresh`, {
        method: "POST",
        credentials: "include",
      })
        .then((refreshResponse) => refreshResponse.ok)
        .catch(() => false)
        .finally(() => { refreshRequest = null; });
    }
    if (await refreshRequest) return api<T>(path, init, false);
  }
  if (!response.ok) {
    let message = "So'rovni bajarib bo'lmadi. Qayta urinib ko'ring.";
    try {
      const body = await response.json();
      message = body.error?.message || body.detail || message;
    } catch {
      // Use the generic message for non-JSON responses.
    }
    const retryAfterValue = response.headers.get("Retry-After");
    throw new ApiError(
      String(message),
      response.status,
      retryAfterValue ? Number(retryAfterValue) : null,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function login(username: string, password: string): Promise<AdminUser> {
  return api("/auth/admin/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function getAdmin(): Promise<AdminUser> {
  return api("/auth/admin/me");
}

export function logout(): Promise<void> {
  return api("/auth/admin/logout", { method: "POST" });
}

export function getStats(): Promise<AdminStats> {
  return api("/admin/stats");
}

export function getLeads(params: URLSearchParams): Promise<Page<Lead>> {
  const query = params.toString();
  return api(`/admin/leads${query ? `?${query}` : ""}`);
}

export function getLead(id: number): Promise<Lead> {
  return api(`/admin/leads/${id}`);
}

export function updateLead(
  id: number,
  payload: Partial<Pick<Lead, "status" | "internal_note">>,
): Promise<Lead> {
  return api(`/admin/leads/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function exportLeads(params: URLSearchParams): Promise<Blob> {
  const query = params.toString();
  return fetch(`${API_ROOT}/admin/leads/export${query ? `?${query}` : ""}`, {
    credentials: "include",
  }).then(async (response) => {
    if (!response.ok) throw new ApiError("CSV eksportini yuklab bo'lmadi.", response.status);
    return response.blob();
  });
}

export function getCars(): Promise<Car[]> {
  return api("/admin/cars");
}

export function saveCar(
  car: Partial<Car>,
  id?: number,
): Promise<Car> {
  return api(id ? `/admin/cars/${id}` : "/admin/cars", {
    method: id ? "PATCH" : "POST",
    body: JSON.stringify(car),
  });
}

export function deleteCar(id: number): Promise<void> {
  return api(`/admin/cars/${id}`, { method: "DELETE" });
}

export function setCarActive(id: number, is_active: boolean): Promise<Car> {
  return api(`/admin/cars/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ is_active }),
  });
}

export function reorderCars(ids: number[]): Promise<void> {
  return api("/admin/cars/reorder", {
    method: "PUT",
    body: JSON.stringify({ ids }),
  });
}

export function addTrim(carId: number, payload: { name: string; price: number | null }): Promise<unknown> {
  return api(`/admin/cars/${carId}/trims`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTrim(
  id: number,
  payload: { name?: string; price?: number | null; sort_order?: number },
): Promise<unknown> {
  return api(`/admin/trims/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteTrim(id: number): Promise<void> {
  return api(`/admin/trims/${id}`, { method: "DELETE" });
}

export function uploadCarImages(carId: number, files: File[]): Promise<unknown> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  return api(`/admin/cars/${carId}/images`, { method: "POST", body });
}

export function setCover(carId: number, imageId: number): Promise<unknown> {
  return api(`/admin/cars/${carId}/images/${imageId}/cover`, { method: "POST" });
}

export function reorderImages(carId: number, ids: number[]): Promise<void> {
  return api(`/admin/cars/${carId}/images/reorder`, {
    method: "PUT",
    body: JSON.stringify({ ids }),
  });
}

export function deleteImage(carId: number, imageId: number): Promise<void> {
  return api(`/admin/cars/${carId}/images/${imageId}`, { method: "DELETE" });
}

export function getUsers(params: URLSearchParams): Promise<Page<User>> {
  const query = params.toString();
  return api(`/admin/users${query ? `?${query}` : ""}`);
}

export function setUserBlocked(id: number, is_blocked: boolean): Promise<User> {
  return api(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ is_blocked }),
  });
}

export function sendBroadcast(data: FormData): Promise<{ broadcast_id: string }> {
  return api("/admin/broadcast", { method: "POST", body: data });
}

export function getBroadcastProgress(id: string): Promise<BroadcastProgress> {
  return api(`/admin/broadcast/${encodeURIComponent(id)}`);
}

export function getSettings(): Promise<AppSettings> {
  return api("/admin/settings");
}

export function saveSettings(payload: AppSettings): Promise<AppSettings> {
  return api("/admin/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getAudit(params: URLSearchParams): Promise<Page<AuditEntry>> {
  const query = params.toString();
  return api(`/admin/audit${query ? `?${query}` : ""}`);
}

export function getAdminAccounts(): Promise<AdminAccount[]> {
  return api("/admin/admin-users");
}

export function createManager(username: string, password: string): Promise<AdminAccount> {
  return api("/admin/admin-users", {
    method: "POST",
    body: JSON.stringify({ username, password, role: "manager" }),
  });
}

export function resetAdminPassword(id: number, password: string): Promise<void> {
  return api(`/admin/admin-users/${id}/password`, {
    method: "PUT",
    body: JSON.stringify({ password }),
  });
}

export function setAdminActive(id: number, is_active: boolean): Promise<void> {
  return api(`/admin/admin-users/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ is_active }),
  });
}

export function formatNumber(value: number | null | undefined): string {
  return value == null ? "—" : Math.trunc(value).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

export function imageUrl(path: string | null): string {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}/${path.replace(/^\/+/, "")}`;
}
