import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible_Next } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { META } from "./copy";
import "./globals.css";

const atkinson = Atkinson_Hyperlegible_Next({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-atkinson",
});

export const metadata: Metadata = {
  title: META.title,
  description: META.description,
  openGraph: { title: META.title, description: META.description, type: "website" },
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f9fd" },
    { media: "(prefers-color-scheme: dark)", color: "#0a1122" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={atkinson.variable}>
      <body>
        {children}
        {/* The insights script only exists on Vercel; elsewhere it 404s and logs a console error. */}
        {process.env.VERCEL ? <Analytics /> : null}
      </body>
    </html>
  );
}
