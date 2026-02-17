"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import Cookies from "js-cookie";
import { authApi } from "@/lib/api";

interface User {
    id: number;
    email: string;
    username: string;
    full_name?: string;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (data: { email: string; username: string; password: string; full_name?: string }) => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const savedToken = Cookies.get("token");
        const savedUser = Cookies.get("user");
        if (savedToken && savedUser) {
            try {
                setToken(savedToken);
                setUser(JSON.parse(savedUser));
            } catch {
                Cookies.remove("token");
                Cookies.remove("user");
            }
        }
        setIsLoading(false);
    }, []);

    const login = useCallback(async (email: string, password: string) => {
        const response = await authApi.login({ email, password });
        const { access_token, user: userData } = response.data;
        Cookies.set("token", access_token, { expires: 7 });
        Cookies.set("user", JSON.stringify(userData), { expires: 7 });
        setToken(access_token);
        setUser(userData);
    }, []);

    const register = useCallback(async (data: { email: string; username: string; password: string; full_name?: string }) => {
        const response = await authApi.register(data);
        const { access_token, user: userData } = response.data;
        Cookies.set("token", access_token, { expires: 7 });
        Cookies.set("user", JSON.stringify(userData), { expires: 7 });
        setToken(access_token);
        setUser(userData);
    }, []);

    const logout = useCallback(() => {
        Cookies.remove("token");
        Cookies.remove("user");
        setToken(null);
        setUser(null);
    }, []);

    return (
        <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) throw new Error("useAuth must be used within AuthProvider");
    return context;
}
