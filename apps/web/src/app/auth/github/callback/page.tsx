"use client";

import { useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function GitHubCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const oauth = searchParams.get("oauth");
  const error = searchParams.get("error");

  useEffect(() => {
    if (oauth === "success") {
      toast.success("Signed in with GitHub successfully!");
      router.replace("/dashboard");
    } else if (error) {
      toast.error(
        decodeURIComponent(error).replace(/_/g, " ") ||
          "GitHub sign-in failed. Please try again.",
      );
      router.replace("/login");
    } else {
      router.replace("/login");
    }
  }, [oauth, error, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  );
}
