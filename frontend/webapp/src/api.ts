import type { Car, Contacts, CreditResult, LeadType } from "./types";
import { t } from "./i18n";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const API_ROOT = `${API_BASE}/api/v1`;
let telegramInitData: string | null = null;
let activeToken: string | null = null;
let tokenRefresh: Promise<string | null> | null = null;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  token?: string,
  init: RequestInit = {},
  retryAfterAuth = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  const accessToken = token || activeToken;
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers,
  });
  if (
    response.status === 401
    && retryAfterAuth
    && accessToken
    && telegramInitData
    && path !== "/auth/telegram"
  ) {
    if (!tokenRefresh) {
      tokenRefresh = authenticate(telegramInitData)
        .then((result) => result.access_token)
        .catch(() => null)
        .finally(() => { tokenRefresh = null; });
    }
    const refreshedToken = await tokenRefresh;
    if (refreshedToken) return request(path, refreshedToken, init, false);
  }

  if (!response.ok) {
    let message = t("genericError");
    try {
      const body = await response.json();
      message = body.error?.message || body.detail || message;
    } catch {
      // Keep the generic message when the server response is not JSON.
    }
    throw new ApiError(String(message), response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function authenticate(initData: string): Promise<{ access_token: string }> {
  telegramInitData = initData;
  return request<{ access_token: string }>("/auth/telegram", undefined, {
    method: "POST",
    body: JSON.stringify({ init_data: initData }),
  }).then((result) => {
    activeToken = result.access_token;
    return result;
  });
}

export function getCars(token: string, search = ""): Promise<Car[]> {
  const params = new URLSearchParams();
  if (search.trim()) params.set("q", search.trim());
  const query = params.size ? `?${params}` : "";
  return request(`/cars${query}`, token);
}

export function getCar(token: string, slug: string): Promise<Car> {
  return request(`/cars/${encodeURIComponent(slug)}`, token);
}

export function getComparedCars(token: string, ids: number[]): Promise<Car[]> {
  return request(`/cars/compare?ids=${ids.join(",")}`, token);
}

export function getFavorites(token: string): Promise<Car[]> {
  return request("/favorites", token);
}

export function addFavorite(token: string, carId: number): Promise<void> {
  return request(`/favorites/${carId}`, token, { method: "PUT" });
}

export function removeFavorite(token: string, carId: number): Promise<void> {
  return request(`/favorites/${carId}`, token, { method: "DELETE" });
}

export function getContacts(token: string): Promise<Contacts> {
  return request("/contacts", token);
}

export function calculateCredit(
  token: string,
  carId: number,
  trimId: number,
  initialPercent: number,
  months: number,
): Promise<CreditResult> {
  return request("/credit/calculate", token, {
    method: "POST",
    body: JSON.stringify({
      car_id: carId,
      trim_id: trimId,
      initial_percent: initialPercent,
      months,
    }),
  });
}

export interface LeadPayload {
  name: string;
  phone: string;
  type: LeadType;
  car_id: number | null;
  trim_id: number | null;
  comment: string | null;
}

export function createLead(token: string, lead: LeadPayload): Promise<{ id: number }> {
  return request("/leads", token, {
    method: "POST",
    body: JSON.stringify(lead),
  });
}

export function imageUrl(path: string | null | undefined): string | undefined {
  if (!path) return undefined;
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}/${path.replace(/^\/+/, "")}`;
}

export function formatPrice(price: number | null): string {
  if (price === null) return t("laterPrice");
  const formatted = Math.trunc(price)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `${formatted} so'm`;
}

export function startingPrice(car: Car): number | null {
  const prices = car.trims
    .filter((trim) => trim.is_active !== false && trim.price !== null)
    .map((trim) => trim.price as number);
  return prices.length ? Math.min(...prices) : null;
}
