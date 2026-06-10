"use client";

import { useEffect, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useCurrentUser } from "@/hooks/use-auth";
import { useAuthStore } from "@/stores/auth-store";
import { DashboardSidebar } from "@/components/dashboard/sidebar";
import { DashboardHeader } from "@/components/dashboard/header";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Menu } from "lucide-react";
import { VerifyEmailBanner } from "@/components/auth/verify-email-banner";
import { listenForAuthExpired } from "@/lib/auth-refresh";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { data: user, isLoading, isError } = useCurrentUser();
  const { isLoaded } = useAuthStore();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const goToLogin = useCallback(() => {
    router.push("/login");
  }, [router]);

  useEffect(() => {
    if (isLoaded && !isLoading && !user) {
      goToLogin();
    }
  }, [isLoaded, isLoading, user, goToLogin]);

  useEffect(() => {
    return listenForAuthExpired(goToLogin);
  }, [goToLogin]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="space-y-4 w-full max-w-md px-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-72" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  if (isError || !user) {
    return null;
  }

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <div className="hidden md:flex">
        <DashboardSidebar />
      </div>

      {/* Mobile sidebar */}
      <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="fixed left-4 top-3 z-40 md:hidden"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="p-0 w-64">
          <DashboardSidebar />
        </SheetContent>
      </Sheet>

      {/* Main content */}
      <div className="flex flex-1 flex-col">
        <DashboardHeader onMenuClick={() => setMobileMenuOpen(true)} />
        {!user.email_verified && <VerifyEmailBanner />}
        <main className="flex-1 p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
