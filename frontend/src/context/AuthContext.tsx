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
    mfa_enabled?: boolean;
}

// Result of login(): either MFA is required (no tokens set yet, caller must
// finish via verifyMfa) or the session is fully established (mfaRequired:false).
type LoginResult =
    | { mfaRequired: true; mfaToken: string }
    | { mfaRequired: false };

interface AuthContextType {
    user: User | null;
    token: string | null;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<LoginResult>;
    verifyMfa: (mfaToken: string, code: string) => Promise<void>;
    register: (data: { email: string; username: string; password: string; full_name?: string; invitation_token?: string }) => Promise<void>;
    logout: () => Promise<void>;
    setTokensFromOAuth: (accessToken: string, refreshToken: string, userData: User) => void;
    setUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUserState] = useState<User | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const savedToken = Cookies.get("token");
        const savedUser = Cookies.get("user");
        const savedRefreshToken = Cookies.get("refresh_token");

        if (savedToken && savedUser) {
            try {
                setToken(savedToken);
                setUserState(JSON.parse(savedUser));
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
                    setUserState(userData);
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

    // Persist a full session (cookies + in-memory state). Shared by the
    // password login, the MFA second step, register, and OAuth so the cookie
    // options stay identical in every entry path.
    const establishSession = useCallback(
        (accessToken: string, refreshToken: string, userData: User) => {
            Cookies.set("token", accessToken, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 1 / 48 });
            Cookies.set("refresh_token", refreshToken, { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
            Cookies.set("user", JSON.stringify(userData), { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
            setToken(accessToken);
            setUserState(userData);
        },
        [],
    );

    // Public setter: update the in-memory user AND re-persist the user cookie
    // so a state change (e.g. mfa_enabled flipping after enroll/disable)
    // survives a reload. Token cookies are left untouched.
    const setUser = useCallback((userData: User) => {
        Cookies.set("user", JSON.stringify(userData), { sameSite: "Strict", secure: process.env.NODE_ENV === "production", expires: 7 });
        setUserState(userData);
    }, []);

    const login = useCallback(async (email: string, password: string): Promise<LoginResult> => {
        const response = await authApi.login({ email, password });
        // MFA challenge: server returns only a short-lived mfa_token and sets
        // NO cookies. The caller must finish via verifyMfa(mfaToken, code).
        if (response.data?.mfa_required) {
            return { mfaRequired: true, mfaToken: response.data.mfa_token };
        }
        const { access_token, refresh_token, user: userData } = response.data;
        establishSession(access_token, refresh_token, userData);
        return { mfaRequired: false };
    }, [establishSession]);

    // Second step of an MFA login: exchange the mfa_token + TOTP/backup code
    // for a real token pair, then establish the session exactly like login().
    const verifyMfa = useCallback(async (mfaToken: string, code: string): Promise<void> => {
        const response = await authApi.verifyMfa(mfaToken, code);
        const { access_token, refresh_token, user: userData } = response.data;
        establishSession(access_token, refresh_token, userData);
    }, [establishSession]);

    const register = useCallback(async (data: { email: string; username: string; password: string; full_name?: string; invitation_token?: string }) => {
        const response = await authApi.register(data);
        const { access_token, refresh_token, user: userData } = response.data;
        establishSession(access_token, refresh_token, userData);
    }, [establishSession]);

    const setTokensFromOAuth = useCallback((accessToken: string, refreshToken: string, userData: User) => {
        establishSession(accessToken, refreshToken, userData);
    }, [establishSession]);

    const logout = useCallback(async () => {
        setLoggingOut(true);
        const refreshToken = Cookies.get("refresh_token");
        // Clear cookies FIRST to prevent interceptor from reading them during logout
        Cookies.remove("token");
        Cookies.remove("refresh_token");
        Cookies.remove("user");
        setToken(null);
        setUserState(null);
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
        <AuthContext.Provider value={{ user, token, isLoading, login, verifyMfa, register, logout, setTokensFromOAuth, setUser }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) throw new Error("useAuth must be used within AuthProvider");
    return context;
}
