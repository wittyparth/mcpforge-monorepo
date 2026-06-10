"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Server,
  Settings,
  Users,
  ChevronLeft,
  ChevronRight,
  Cable,
  KeyRound,
  CreditCard,
} from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const navItems = [
  {
    title: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    title: "Servers",
    href: "/dashboard/servers",
    icon: Server,
  },
  {
    title: "Team",
    href: "/dashboard/team",
    icon: Users,
  },
  {
    title: "Billing",
    href: "/dashboard/billing",
    icon: CreditCard,
  },
  {
    title: "Settings",
    href: "/dashboard/settings",
    icon: Settings,
  },
  {
    title: "API Keys",
    href: "/dashboard/settings/api-keys",
    icon: KeyRound,
  },
] as const;

export function DashboardSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "flex flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-300",
        collapsed ? "w-16" : "w-64",
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
        <Cable className="h-6 w-6 shrink-0 text-sidebar-primary" />
        {!collapsed && (
          <span className="font-semibold tracking-tight">MCPForge</span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                collapsed && "justify-center px-2",
              )}
              title={collapsed ? item.title : undefined}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.title}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <Separator className="bg-sidebar-border" />
      <div className="p-3">
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "default"}
          className={cn(
            "w-full text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
            collapsed && "h-9 w-9 mx-auto",
          )}
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" />
              <span>Collapse</span>
            </>
          )}
        </Button>
      </div>
    </aside>
  );
}
