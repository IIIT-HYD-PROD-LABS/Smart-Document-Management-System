import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import Cookies from "js-cookie";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
    baseURL: `${API_URL}/api`,
    headers: {
        "Content-Type": "application/json",
    },
});

// ──── Token refresh queue pattern ────
// Prevents multiple concurrent refresh requests when several 401s arrive simultaneously.

let isRefreshing = false;
let isLoggingOut = false;

export function setLoggingOut(value: boolean) { isLoggingOut = value; }

let failedQueue: Array<{
    resolve: (token: string) => void;
    reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null) {
    failedQueue.forEach((promise) => {
        if (error) {
            promise.reject(error);
        } else {
            promise.resolve(token!);
        }
    });
    failedQueue = [];
}

// Attach access token to every request
api.interceptors.request.use((config) => {
    const token = Cookies.get("token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Handle 401 responses with silent refresh
api.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & {
            _retry?: boolean;
        };

        // Only attempt refresh on 401, only once per request, and not during logout
        if (error.response?.status !== 401 || originalRequest._retry || isLoggingOut) {
            return Promise.reject(error);
        }

        // If a refresh is already in progress, queue this request
        if (isRefreshing) {
            return new Promise<string>((resolve, reject) => {
                failedQueue.push({ resolve, reject });
            }).then((newToken) => {
                originalRequest.headers.Authorization = `Bearer ${newToken}`;
                return api(originalRequest);
            });
        }

        originalRequest._retry = true;
        isRefreshing = true;

        const refreshToken = Cookies.get("refresh_token");

        if (!refreshToken) {
            // No refresh token available -- clear state and redirect
            isRefreshing = false;
            processQueue(error, null);
            Cookies.remove("token");
            Cookies.remove("refresh_token");
            Cookies.remove("user");
            if (typeof window !== "undefined") {
                window.location.href = "/login";
            }
            return Promise.reject(error);
        }

        try {
            // Use raw axios (NOT the api instance) to avoid interceptor loops
            const response = await axios.post(`${API_URL}/api/auth/refresh`, {
                refresh_token: refreshToken,
            });

            const { access_token, refresh_token: newRefreshToken, user } = response.data;

            // Update cookies with new tokens
            Cookies.set("token", access_token, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 1 / 48 });
            Cookies.set("refresh_token", newRefreshToken, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
            Cookies.set("user", JSON.stringify(user), { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });

            // Retry all queued requests with the new token
            processQueue(null, access_token);

            // Retry the original request
            originalRequest.headers.Authorization = `Bearer ${access_token}`;
            return api(originalRequest);
        } catch (refreshError) {
            // Refresh failed -- clear everything and redirect to login
            processQueue(refreshError, null);
            Cookies.remove("token");
            Cookies.remove("refresh_token");
            Cookies.remove("user");
            if (typeof window !== "undefined") {
                window.location.href = "/login";
            }
            return Promise.reject(refreshError);
        } finally {
            isRefreshing = false;
        }
    }
);

// ──── Auth API ────
export const authApi = {
    register: (data: { email: string; username: string; password: string; full_name?: string }) =>
        api.post("/auth/register", data),

    login: (data: { email: string; password: string }) =>
        api.post("/auth/login", data),

    refresh: (refreshToken: string) =>
        axios.post(`${API_URL}/api/auth/refresh`, { refresh_token: refreshToken }),

    logout: (refreshToken: string) =>
        api.post("/auth/logout", { refresh_token: refreshToken }),

    getProviders: () =>
        api.get("/auth/providers"),
};

// ──── Documents API ────
export const documentsApi = {
    upload: (file: File, onProgress?: (percent: number) => void) => {
        const formData = new FormData();
        formData.append("file", file);
        return api.post("/documents/upload", formData, {
            headers: { "Content-Type": "multipart/form-data" },
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const percent = Math.round(
                        (progressEvent.loaded * 100) / progressEvent.total
                    );
                    onProgress(percent);
                }
            },
        });
    },

    getStatus: (documentId: number) =>
        api.get(`/documents/${documentId}/status`),

    getAll: (page = 1, perPage = 50) =>
        api.get(`/documents/all?page=${page}&per_page=${perPage}`),

    getById: (id: number) =>
        api.get(`/documents/${id}`),

    getByCategory: (category: string) =>
        api.get(`/documents/category/${category}`),

    search: (
        query: string,
        category?: string,
        dateFrom?: string,
        dateTo?: string,
        amountMin?: number,
        amountMax?: number,
    ) => {
        const params = new URLSearchParams({ q: query });
        if (category) params.append("category", category);
        if (dateFrom) params.append("date_from", dateFrom);
        if (dateTo) params.append("date_to", dateTo);
        if (amountMin !== undefined) params.append("amount_min", String(amountMin));
        if (amountMax !== undefined) params.append("amount_max", String(amountMax));
        return api.get(`/documents/search?${params.toString()}`);
    },

    getStats: () =>
        api.get("/documents/stats"),

    delete: (id: number) =>
        api.delete(`/documents/${id}`),

    saveHighlights: (id: number, highlights: Array<{ text: string; start: number; end: number }>) =>
        api.put(`/documents/${id}/highlights`, highlights),

    batchDelete: (ids: number[]) =>
        api.post("/documents/batch-delete", ids),
};

// ──── ML API ────
export const mlApi = {
    getEvaluation: () => api.get("/ml/evaluation"),
};

// ──── Admin API ────
export const adminApi = {
    getUsers: (page = 1, perPage = 20, search?: string) => {
        const params = new URLSearchParams({ page: String(page), per_page: String(perPage) });
        if (search) params.append("search", search);
        return api.get(`/admin/users?${params.toString()}`);
    },

    getUser: (id: number) =>
        api.get(`/admin/users/${id}`),

    updateRole: (id: number, role: string) =>
        api.patch(`/admin/users/${id}/role`, { role }),

    updateStatus: (id: number, isActive: boolean) =>
        api.patch(`/admin/users/${id}/status`, { is_active: isActive }),

    getStats: () =>
        api.get("/admin/stats"),
};

// ──── Sharing API ────
export const sharingApi = {
    share: (documentId: number, email: string, permission: string = "view") =>
        api.post(`/documents/${documentId}/share`, { email, permission }),

    getPermissions: (documentId: number) =>
        api.get(`/documents/${documentId}/permissions`),

    revoke: (documentId: number, permissionId: number) =>
        api.delete(`/documents/${documentId}/share/${permissionId}`),

    getSharedWithMe: (page = 1, perPage = 20) =>
        api.get(`/documents/shared-with-me?page=${page}&per_page=${perPage}`),
};

// ──── OAuth API ────
export const oauthApi = {
    getProviders: () =>
        api.get("/auth/providers"),

    getGoogleUrl: () =>
        api.get("/auth/oauth/google"),

    getMicrosoftUrl: () =>
        api.get("/auth/oauth/microsoft"),

    exchangeCode: (code: string, token: string) =>
        api.post("/auth/oauth/exchange", { code, token }),
};

export default api;
