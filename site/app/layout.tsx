import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { META } from "./copy";
import "./globals.css";

// Inter matches heyclicky exactly; the owner's "exactly like heyclicky" wins over the usual reject list (BRIEF-v3 §1).
const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });

// Social previews need absolute image URLs; on Vercel use the production domain.
const productionHost = process.env.VERCEL_PROJECT_PRODUCTION_URL;

export const metadata: Metadata = {
  metadataBase: productionHost ? new URL(`https://${productionHost}`) : undefined,
  title: META.title,
  description: META.description,
  openGraph: {
    title: META.ogTitle,
    description: META.description,
    type: "website",
    url: "/",
    siteName: "zoya",
    // Plain JPEG with no query string: WhatsApp drops large PNG or query-string preview images.
    images: [{ url: "/og.jpg", width: 1200, height: 630, type: "image/jpeg", alt: META.ogImageAlt }],
  },
  twitter: {
    card: "summary_large_image",
    title: META.ogTitle,
    description: META.description,
    images: [{ url: "/og.jpg", alt: META.ogImageAlt }],
  },
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
