import type { Metadata, Viewport } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Props FR vs FanDuel — Tennis & WNBA",
  description:
    "Compare les cotes tennis (aces, breaks, victoires) et basket WNBA (props joueuses) des books FR contre FanDuel.",
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
