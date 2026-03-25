import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    const token = request.cookies.get("token")?.value;
    const refreshToken = request.cookies.get("refresh_token")?.value;
    const isAuthenticated = Boolean(token || refreshToken);

    if (pathname.startsWith("/dashboard")) {
        if (!isAuthenticated) {
            const loginUrl = new URL("/login", request.url);
            loginUrl.searchParams.set("redirect", pathname);
            return NextResponse.redirect(loginUrl);
        }
    }

    if (pathname === "/login" || pathname === "/register") {
        if (isAuthenticated) {
            return NextResponse.redirect(new URL("/dashboard", request.url));
        }
    }

    return NextResponse.next();
}

export const config = {
    matcher: ["/dashboard/:path*", "/login", "/register"],
};
