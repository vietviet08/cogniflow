import type { ReactNode } from "react";
import { Inter } from "next/font/google";

import { Providers } from "@/components/providers";
import { Sidebar } from "@/components/layout/sidebar";
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
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <main className="flex flex-1 flex-col overflow-y-auto">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
