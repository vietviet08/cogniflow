"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { appRoutes } from "@/lib/routes";

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary">
      <ul style={{ display: "flex", gap: 16, listStyle: "none", padding: 0 }}>
        {appRoutes.map((route) => {
          const active = pathname.startsWith(route.href);
          return (
            <li key={route.href}>
              <Link href={route.href} style={{ fontWeight: active ? 700 : 400 }}>
                {route.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
