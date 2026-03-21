import Link from "next/link";

import { appRoutes } from "@/lib/routes";

export default function HomePage() {
  return (
    <section>
      <h2>Workspace Shell</h2>
      <p>Use the sections below to start building research workflows.</p>
      <ul>
        {appRoutes.map((route) => (
          <li key={route.href}>
            <Link href={route.href}>{route.label}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
