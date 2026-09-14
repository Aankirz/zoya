import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { META } from "./copy";
import "./globals.css";

// Inter matches heyclicky exactly; the owner's "exactly like heyclicky" wins over the usual reject list (BRIEF-v3 §1).
const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });

export const metadata: Metadata = {
  title: META.title,
  description: META.description,
  openGraph: { title: META.title, description: META.description, type: "website" },
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#f5f5f5",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        {children}
        {/* The insights script only exists on Vercel; elsewhere it 404s and logs a console error. */}
        {process.env.VERCEL ? <Analytics /> : null}
      </body>
    </html>
  );
}
