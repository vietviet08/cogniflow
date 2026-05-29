import type { ReactNode } from "react";
import { Inter, Space_Grotesk } from "next/font/google";

import { RootShell } from "@/components/layout/root-shell";
import { Providers } from "@/components/providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
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
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${spaceGrotesk.variable}`}>
      <body className="text-foreground antialiased">
        <Providers>
          <RootShell>{children}</RootShell>
        </Providers>
      </body>
    </html>
  );
}
