"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { listOrganizations } from "@/lib/api/client";
import type { OrganizationData } from "@/lib/api/types";
import { useAuth } from "@/components/auth-provider";

interface OrganizationContextValue {
    organizations: OrganizationData[];
    activeOrganization: OrganizationData | null;
    isLoading: boolean;
    setActiveOrganizationId: (id: string) => void;
}

const OrganizationContext = createContext<OrganizationContextValue | null>(null);

const STORAGE_KEY = "notemesh_active_organization_id";

export function OrganizationProvider({ children }: Readonly<{ children: ReactNode }>) {
    const { user } = useAuth();
    const [activeOrganizationId, setActiveId] = useState<string | null>(null);

    const { data, isLoading } = useQuery({
        queryKey: ["organizations", user?.id],
        queryFn: async () => {
            if (!user) return { items: [], total: 0 };
            const res = await listOrganizations();
            return res.data;
        },
        enabled: !!user,
    });

    const organizations = data?.items ?? [];

    useEffect(() => {
        if (!user) {
            setActiveId(null);
            return;
        }
        if (organizations.length > 0) {
            const stored = globalThis.localStorage?.getItem(STORAGE_KEY);
            const foundStored = organizations.find((o) => o.id === stored);
            
            if (foundStored) {
                setActiveId(stored);
            } else if (!activeOrganizationId || !organizations.find(o => o.id === activeOrganizationId)) {
                // Default to the first one if not set or invalid
                setActiveId(organizations[0].id);
                globalThis.localStorage?.setItem(STORAGE_KEY, organizations[0].id);
            }
        }
    }, [organizations, user, activeOrganizationId]);

    const setActiveOrganizationId = (id: string) => {
        setActiveId(id);
        globalThis.localStorage?.setItem(STORAGE_KEY, id);
    };

    const activeOrganization = organizations.find((o) => o.id === activeOrganizationId) ?? null;

    return (
        <OrganizationContext.Provider
            value={{
                organizations,
                activeOrganization,
                isLoading,
                setActiveOrganizationId,
            }}
        >
            {children}
        </OrganizationContext.Provider>
    );
}

export function useOrganization(): OrganizationContextValue {
    const context = useContext(OrganizationContext);
    if (!context) {
        throw new Error("useOrganization must be used within OrganizationProvider");
    }
    return context;
}
