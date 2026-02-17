import axios from "axios";
import Cookies from "js-cookie";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
    baseURL: `${API_URL}/api`,
    headers: {
        "Content-Type": "application/json",
    },
});

// Attach token to every request
api.interceptors.request.use((config) => {
    const token = Cookies.get("token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Handle 401 responses
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            Cookies.remove("token");
            if (typeof window !== "undefined") {
                window.location.href = "/login";
            }
        }
        return Promise.reject(error);
    }
);

// ──── Auth API ────
export const authApi = {
    register: (data: { email: string; username: string; password: string; full_name?: string }) =>
        api.post("/auth/register", data),

    login: (data: { email: string; password: string }) =>
        api.post("/auth/login", data),
};

// ──── Documents API ────
export const documentsApi = {
    upload: (file: File) => {
        const formData = new FormData();
        formData.append("file", file);
        return api.post("/documents/upload", formData, {
            headers: { "Content-Type": "multipart/form-data" },
        });
    },

    getAll: (skip = 0, limit = 50) =>
        api.get(`/documents/all?skip=${skip}&limit=${limit}`),

    getById: (id: number) =>
        api.get(`/documents/${id}`),

    getByCategory: (category: string) =>
        api.get(`/documents/category/${category}`),

    search: (query: string, category?: string) =>
        api.post("/documents/search", { query, category }),

    getStats: () =>
        api.get("/documents/stats"),

    delete: (id: number) =>
        api.delete(`/documents/${id}`),
};

export default api;
