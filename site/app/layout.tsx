import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible_Mono, Atkinson_Hyperlegible_Next, Host_Grotesk, Italianno } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { META } from "./copy";
import "./globals.css";

const atkinson = Atkinson_Hyperlegible_Next({ subsets: ["latin"], display: "swap", variable: "--font-atkinson" });
const atkinsonMono = Atkinson_Hyperlegible_Mono({ subsets: ["latin"], display: "swap", variable: "--font-mono" });
const hostGrotesk = Host_Grotesk({ subsets: ["latin"], display: "swap", variable: "--font-grotesk" });
// Script for the name only; the name is also real text in the title, intro and footer.
const italianno = Italianno({ subsets: ["latin"], weight: "400", display: "swap", variable: "--font-script" });

export const metadata: Metadata = {
  title: META.title,
  description: META.description,
  openGraph: { title: META.title, description: META.description, type: "website" },
};

export const viewport: Viewport = {
  colorScheme: "dark light",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0b0b0d" },
    { media: "(prefers-color-scheme: light)", color: "#f6f3ec" },
  ],
};

const fontVariables = [atkinson, atkinsonMono, hostGrotesk, italianno].map((font) => font.variable).join(" ");

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={fontVariables}>
      <body>
        {children}
        {/* The insights script only exists on Vercel; elsewhere it 404s and logs a console error. */}
        {process.env.VERCEL ? <Analytics /> : null}
      </body>
    </html>
  );
}
