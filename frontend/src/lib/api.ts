export type Json =
  null | boolean | number | string | Json[] | { [key: string]: Json };
export type Row = { id: string; version: number; [key: string]: unknown };
export type Collection<T = Row> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};
export type Session = {
  user: {
    id: string;
    name: string;
    email: string;
    kind: string;
    [key: string]: unknown;
  };
  permissions: string[];
};
let token = "";
let refreshing: Promise<boolean> | null = null;
export const setToken = (value: string) => {
  token = value;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public details: { field: string; message: string }[] = [],
    public requestId = "",
  ) {
    super(message);
  }
}
async function refresh() {
  if (!refreshing)
    refreshing = fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
    })
      .then(async (r) => {
        if (!r.ok) return false;
        const body = (await r.json()) as { access_token: string };
        token = body.access_token;
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  return refreshing;
}
async function request(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", "Bearer " + token);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch("/api/v1" + path, {
      ...init,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError(
      "Não foi possível conectar ao servidor. Verifique sua conexão.",
      0,
    );
  }
  if (
    response.status === 401 &&
    retry &&
    !path.startsWith("/auth/login") &&
    !path.startsWith("/auth/refresh")
  ) {
    if (await refresh()) return request(path, init, false);
  }
  if (!response.ok) {
    const error = (await response
      .json()
      .catch(() => ({ message: "Não foi possível concluir a operação." }))) as {
      message?: string;
      details?: { field: string; message: string }[];
      request_id?: string;
    };
    throw new ApiError(
      error.message ?? "Não foi possível concluir a operação.",
      response.status,
      error.details,
      error.request_id,
    );
  }
  return response;
}
export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const response = await request(path, init, retry);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const put = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "PUT", body: JSON.stringify(body) });
export async function download(path: string, filename: string) {
  const response = await request(path);
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
export async function documentBlob(path: string) {
  return (await request(path)).blob();
}
export async function imageData(path: string) {
  const response = await request(path);
  const blob = await response.blob();
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Não foi possível carregar a foto."));
    reader.readAsDataURL(blob);
  });
}
export const str = (value: unknown) => (value == null ? "" : String(value));
export const obj = (value: unknown) =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
export const rows = (value: unknown) =>
  Array.isArray(value) ? (value as Row[]) : [];
