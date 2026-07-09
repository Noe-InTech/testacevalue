import type { Metadata, Viewport } from "next";

import { Dashboard } from "@/components/Dashboard";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aces FR vs FanDuel",
  description: "Compare les cotes aces des books FR contre FanDuel.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f172a",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
