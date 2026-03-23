"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import Cookies from "js-cookie";
import { authApi, setLoggingOut } from "@/lib/api";

interface User {
    id: number;
    email: string;
    username: string;
    full_name?: string;
    role: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (data: { email: string; username: string; password: string; full_name?: string }) => Promise<void>;
    logout: () => Promise<void>;
    setTokensFromOAuth: (accessToken: string, refreshToken: string, userData: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const savedToken = Cookies.get("token");
        const savedUser = Cookies.get("user");
        const savedRefreshToken = Cookies.get("refresh_token");

        if (savedToken && savedUser) {
            try {
                setToken(savedToken);
                setUser(JSON.parse(savedUser));
            } catch {
                Cookies.remove("token");
                Cookies.remove("refresh_token");
                Cookies.remove("user");
            }
        } else if (!savedToken && savedRefreshToken) {
            // Access token missing but refresh token exists -- attempt silent refresh
            authApi
                .refresh(savedRefreshToken)
                .then((response) => {
                    const { access_token, refresh_token, user: userData } = response.data;
                    Cookies.set("token", access_token, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 1 / 48 });
                    Cookies.set("refresh_token", refresh_token, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
                    Cookies.set("user", JSON.stringify(userData), { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
                    setToken(access_token);
                    setUser(userData);
                })
                .catch(() => {
                    // Refresh failed -- clear everything
                    Cookies.remove("token");
                    Cookies.remove("refresh_token");
                    Cookies.remove("user");
                })
                .finally(() => {
                    setIsLoading(false);
                });
            return; // Skip the setIsLoading(false) below; it runs in .finally()
        }
        setIsLoading(false);
    }, []);

    const login = useCallback(async (email: string, password: string) => {
        const response = await authApi.login({ email, password });
        const { access_token, refresh_token, user: userData } = response.data;
        Cookies.set("token", access_token, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 1 / 48 });
        Cookies.set("refresh_token", refresh_token, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
        Cookies.set("user", JSON.stringify(userData), { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
        setToken(access_token);
        setUser(userData);
    }, []);

    const register = useCallback(async (data: { email: string; username: string; password: string; full_name?: string }) => {
        const response = await authApi.register(data);
        const { access_token, refresh_token, user: userData } = response.data;
        Cookies.set("token", access_token, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 1 / 48 });
        Cookies.set("refresh_token", refresh_token, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
        Cookies.set("user", JSON.stringify(userData), { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
        setToken(access_token);
        setUser(userData);
    }, []);

    const setTokensFromOAuth = useCallback((accessToken: string, refreshToken: string, userData: User) => {
        Cookies.set("token", accessToken, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 1 / 48 });
        Cookies.set("refresh_token", refreshToken, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
        Cookies.set("user", JSON.stringify(userData), { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
        setToken(accessToken);
        setUser(userData);
    }, []);

    const logout = useCallback(async () => {
        setLoggingOut(true);
        const refreshToken = Cookies.get("refresh_token");
        // Clear cookies FIRST to prevent interceptor from reading them during logout
        Cookies.remove("token");
        Cookies.remove("refresh_token");
        Cookies.remove("user");
        setToken(null);
        setUser(null);
        if (refreshToken) {
            try {
                await authApi.logout(refreshToken);
            } catch {
                // Best-effort server-side revocation
            }
        }
        setLoggingOut(false);
    }, []);

    return (
        <AuthContext.Provider value={{ user, token, isLoading, login, register, logout, setTokensFromOAuth }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) throw new Error("useAuth must be used within AuthProvider");
    return context;
}
