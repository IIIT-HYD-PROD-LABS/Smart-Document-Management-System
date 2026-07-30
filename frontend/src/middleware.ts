import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    const token = request.cookies.get("token")?.value;
    const refreshToken = request.cookies.get("refresh_token")?.value;
    const isAuthenticated = Boolean(token || refreshToken);

    // Derive redirect targets from request.nextUrl (basePath-aware) so Next
    // re-applies the /taxsyncfestage basePath on the way out. Using
    // new URL("/login", request.url) would drop the prefix and bounce the
    // browser to canvas.iiit.ac.in/login (the IIIT root).
    if (pathname.startsWith("/dashboard")) {
        if (!isAuthenticated) {
            const loginUrl = request.nextUrl.clone();
            loginUrl.pathname = "/login";
            loginUrl.searchParams.set("redirect", pathname);
            return NextResponse.redirect(loginUrl);
        }
    }

    if (pathname === "/login" || pathname === "/register") {
        if (isAuthenticated) {
            const dashUrl = request.nextUrl.clone();
            dashUrl.pathname = "/dashboard";
            return NextResponse.redirect(dashUrl);
        }
    }

    return NextResponse.next();
}

export const config = {
    matcher: ["/dashboard/:path*", "/login", "/register"],
};
