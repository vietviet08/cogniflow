import type { ReactNode } from "react";
import { Inter } from "next/font/google";

import { RootShell } from "@/components/layout/root-shell";
import { Providers } from "@/components/providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata = {
  title: {
    template: "%s | NoteMesh",
    default: "NoteMesh",
  },
  description: "AI-powered research and knowledge management",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <body className="bg-background text-foreground antialiased">
        <Providers>
          <RootShell>{children}</RootShell>
        </Providers>
      </body>
    </html>
  );
}
