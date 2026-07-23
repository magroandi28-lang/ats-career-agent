import { NextResponse } from "next/server";
import { updateSession } from "./lib/supabase/proxy";

const PUBLIC_PATHS = new Set(["/", "/login", "/auth/confirm"]);

export async function proxy(request) {
  const { response, claims } = await updateSession(request);
  const pathname = request.nextUrl.pathname;

  if (!claims && !PUBLIC_PATHS.has(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (claims && pathname === "/login") {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
