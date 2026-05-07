import { NextResponse, type NextRequest } from "next/server";

export const config = { matcher: ["/app/:path((?!login).*)"] };

export function middleware(req: NextRequest) {
  const cookie = req.cookies.get("kss_owner");
  if (!cookie) {
    const loginUrl = new URL("/app/login", req.url);
    loginUrl.searchParams.set("from", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}
