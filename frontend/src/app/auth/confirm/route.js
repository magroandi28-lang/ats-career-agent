import { NextResponse } from "next/server";
import { createClient } from "../../../lib/supabase/server";

export async function GET(request) {
  const url = new URL(request.url);
  const tokenHash = url.searchParams.get("token_hash");
  const type = url.searchParams.get("type");
  const code = url.searchParams.get("code");
  const redirectTo = request.nextUrl.clone();
  redirectTo.pathname = "/login";
  redirectTo.search = "";

  const supabase = await createClient();
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      redirectTo.pathname = "/";
    }
  } else if (tokenHash && type) {
    const { error } = await supabase.auth.verifyOtp({
      type,
      token_hash: tokenHash,
    });
    if (!error) {
      redirectTo.pathname = "/";
    }
  }

  return NextResponse.redirect(redirectTo);
}
