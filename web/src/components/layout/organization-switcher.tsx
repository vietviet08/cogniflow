"use client";

import { useOrganization } from "@/components/organization-provider";
import { cn } from "@/lib/utils";
import { ChevronsUpDown, Building2 } from "lucide-react";
import { useState, useRef, useEffect } from "react";

interface OrganizationSwitcherProps {
    collapsed?: boolean;
}

export function OrganizationSwitcher({ collapsed }: OrganizationSwitcherProps) {
    const { organizations, activeOrganization, setActiveOrganizationId } = useOrganization();
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    if (organizations.length === 0) return null;

    return (
        <div className="relative mb-4 px-2" ref={containerRef}>
            {!collapsed ? (
                <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    Workspace
                </p>
            ) : null}
            
            <button
                type="button"
                className={cn(
                    "flex w-full items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
                    collapsed && "justify-center px-0 py-2"
                )}
                onClick={() => setIsOpen(!isOpen)}
                title={collapsed ? activeOrganization?.name : undefined}
            >
                <div className="flex items-center gap-2 overflow-hidden">
                    <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                    {!collapsed && (
                        <span className="truncate text-foreground">
                            {activeOrganization?.name ?? "Select Workspace"}
                        </span>
                    )}
                </div>
                {!collapsed && (
                    <ChevronsUpDown className="h-3 w-3 shrink-0 text-muted-foreground" />
                )}
            </button>

            {isOpen && (
                <div className="absolute left-2 right-2 top-full z-50 mt-1 origin-top rounded-md border border-border bg-popover text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95">
                    <div className="flex flex-col p-1">
                        {organizations.map((org) => (
                            <button
                                key={org.id}
                                type="button"
                                className={cn(
                                    "relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
                                    activeOrganization?.id === org.id && "bg-accent/50 text-accent-foreground font-semibold"
                                )}
                                onClick={() => {
                                    setActiveOrganizationId(org.id);
                                    setIsOpen(false);
                                }}
                            >
                                <span className={cn(
                                    "flex items-center gap-2 truncate",
                                    collapsed && "w-8 overflow-hidden" 
                                )}>
                                    {!collapsed ? org.name : org.name.substring(0, 2).toUpperCase()}
                                </span>
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
