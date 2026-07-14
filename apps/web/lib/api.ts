// Thin client for the CartIQ FastAPI backend.
// The JWT is kept in localStorage and attached as a Bearer token.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "cartiq_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---- Types (mirror the backend Pydantic schemas) ----
export interface TokenResponse {
  access_token: string;
  token_type: string;
}
export interface UserResponse {
  id: string;
  email: string;
  created_at: string;
}
export interface ChatMessage {
  role: "user" | "model";
  text: string;
}
export interface ChatResponse {
  reply: string;
  tools_used: string[];
}
export interface CartLineItem {
  id: string;
  name: string;
  quantity: number;
  added_by: "user" | "assistant";
}
export interface CartState {
  items: CartLineItem[];
}
export interface WishlistItem {
  id: string;
  product_name: string;
  product_query: string;
  platform_item_ids: Record<string, string>;
  created_at: string;
}

// ---- Endpoints ----
export const api = {
  register: (email: string, password: string) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<UserResponse>("/auth/me"),

  chat: (message: string, history: ChatMessage[], pincode?: string) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, history, pincode }),
    }),

  cart: {
    get: () => request<CartState>("/cart"),
    add: (name: string, quantity = 1) =>
      request<CartState>("/cart/add", {
        method: "POST",
        body: JSON.stringify({ name, quantity }),
      }),
    updateQty: (id: string, quantity: number) =>
      request<CartState>(`/cart/item/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ quantity }),
      }),
    remove: (id: string) =>
      request<CartState>(`/cart/item/${id}`, { method: "DELETE" }),
    clear: () => request<CartState>("/cart", { method: "DELETE" }),
  },

  wishlist: {
    get: () => request<WishlistItem[]>("/wishlist"),
    add: (name: string) =>
      request<WishlistItem>("/wishlist", {
        method: "POST",
        body: JSON.stringify({ product_name: name, product_query: name }),
      }),
    remove: (id: string) =>
      request<void>(`/wishlist/${id}`, { method: "DELETE" }),
  },
};

export { ApiError };
