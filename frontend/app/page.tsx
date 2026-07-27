"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { authStorage } from "@/lib/api/auth-storage";

/**
 * Root route. The product has no public marketing page yet — this simply
 * routes visitors straight into the app: signed-in users go to the
 * dashboard, everyone else goes to the login form.
 */
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    if (authStorage.getAccessToken()) {
      router.replace("/dashboard");
    } else {
      router.replace("/login");
    }
  }, [router]);

  return null;
}
