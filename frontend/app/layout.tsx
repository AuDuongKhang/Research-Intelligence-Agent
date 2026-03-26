import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Research Intelligence",
  description: "Multi-agent research system with real-time transparency",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
