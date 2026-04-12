"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import {
    FolderOpen,
    Database,
    Search,
    ListChecks,
    Lightbulb,
    FileText,
    KeyRound,
    Moon,
    Sun,
    BrainCircuit,
    LogOut,
    PanelLeftClose,
    PanelLeftOpen,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const navItems = [
    { href: "/projects", label: "Projects", icon: FolderOpen },
    { href: "/sources", label: "Sources", icon: Database },
    { href: "/jobs", label: "Jobs", icon: ListChecks },
    { href: "/query", label: "Query", icon: Search },
    { href: "/settings", label: "Settings", icon: KeyRound },
    { href: "/insights", label: "Insights", icon: Lightbulb },
    { href: "/reports", label: "Reports", icon: FileText },
];

export function Sidebar() {
    const pathname = usePathname();
    const { theme, setTheme } = useTheme();
    const { user, logout } = useAuth();
    const [collapsed, setCollapsed] = useState(false);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        const saved = window.localStorage.getItem("notemesh.sidebar.collapsed");
        setCollapsed(saved === "true");
    }, []);

    function toggleCollapsed() {
        setCollapsed((current) => {
            const next = !current;
            if (typeof window !== "undefined") {
                window.localStorage.setItem(
                    "notemesh.sidebar.collapsed",
                    String(next),
                );
            }
            return next;
        });
    }

    return (
        <aside
            className={cn(
                "relative flex h-screen shrink-0 flex-col border-r border-border bg-card transition-[width] duration-200",
                collapsed ? "w-[4.5rem]" : "w-60",
            )}
        >
            <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={toggleCollapsed}
                className="absolute -right-4 top-14 z-20 h-8 w-8 rounded-full border-border bg-background shadow-sm"
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
                {collapsed ? (
                    <PanelLeftOpen className="h-4 w-4" />
                ) : (
                    <PanelLeftClose className="h-4 w-4" />
                )}
            </Button>

            {/* Logo */}
            <div
                className={cn(
                    "flex items-center border-b border-border py-5",
                    collapsed ? "justify-center px-3" : "gap-2.5 px-5",
                )}
            >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                    <BrainCircuit className="h-4 w-4" />
                </div>
                {!collapsed ? (
                    <div className="flex min-w-0 flex-1 flex-col leading-tight">
                        <span className="text-sm font-semibold text-foreground">
                            NoteMesh
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                            AI Research
                        </span>
                    </div>
                ) : null}
            </div>

            {/* Navigation */}
            <nav
                className={cn(
                    "flex flex-1 flex-col gap-1 overflow-y-auto py-4",
                    collapsed ? "px-2" : "px-3",
                )}
            >
                {!collapsed ? (
                    <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                        Workspace
                    </p>
                ) : null}
                {navItems.map(({ href, label, icon: Icon }) => {
                    const active = pathname.startsWith(href);
                    return (
                        <Link
                            key={href}
                            href={href}
                            title={collapsed ? label : undefined}
                            className={cn(
                                "group flex items-center rounded-lg text-sm font-medium transition-all duration-150",
                                collapsed
                                    ? "justify-center px-2 py-2.5"
                                    : "gap-3 px-3 py-2",
                                active
                                    ? "bg-primary/10 text-primary"
                                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                            )}
                        >
                            <Icon
                                className={cn(
                                    "h-4 w-4 shrink-0 transition-colors",
                                    active
                                        ? "text-primary"
                                        : "text-muted-foreground group-hover:text-foreground",
                                )}
                            />
                            {!collapsed ? label : null}
                            {active && !collapsed && (
                                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* Footer */}
            <div
                className={cn(
                    "border-t border-border py-3",
                    collapsed ? "px-2" : "px-3",
                )}
            >
                {!collapsed && user ? (
                    <div className="mb-2 rounded-md border border-border bg-muted/30 px-3 py-2">
                        <p className="text-xs font-medium text-foreground truncate">
                            {user.display_name}
                        </p>
                        <p className="text-[11px] text-muted-foreground truncate">
                            {user.email}
                        </p>
                    </div>
                ) : null}
                <Button
                    variant="ghost"
                    size="sm"
                    className={cn(
                        "w-full text-muted-foreground",
                        collapsed
                            ? "justify-center px-0"
                            : "justify-start gap-2",
                    )}
                    onClick={() =>
                        setTheme(theme === "dark" ? "light" : "dark")
                    }
                    title={collapsed ? "Toggle theme" : undefined}
                >
                    <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
                    <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
                    {!collapsed ? (
                        <span className="text-sm">Toggle theme</span>
                    ) : null}
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    className={cn(
                        "w-full text-muted-foreground",
                        collapsed
                            ? "mt-1 justify-center px-0"
                            : "mt-1 justify-start gap-2",
                    )}
                    onClick={logout}
                    title={collapsed ? "Log out" : undefined}
                >
                    <LogOut className="h-4 w-4" />
                    {!collapsed ? (
                        <span className="text-sm">Log out</span>
                    ) : null}
                </Button>
            </div>
        </aside>
    );
}
