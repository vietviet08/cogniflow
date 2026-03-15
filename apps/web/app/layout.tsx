import type { ReactNode } from "react";

import { Navigation } from "@/components/navigation";

export const metadata = {
  title: "NoteMesh",
  description: "AI research infrastructure shell",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif" }}>
        <header style={{ borderBottom: "1px solid #ddd", padding: 16 }}>
          <h1 style={{ margin: 0, fontSize: 24 }}>NoteMesh</h1>
          <p style={{ marginTop: 4, color: "#555" }}>AI research infrastructure</p>
          <Navigation />
        </header>
        <main style={{ padding: 16 }}>{children}</main>
      </body>
    </html>
  );
}
