import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PRScope",
  description: "GitHub PR Intelligence Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`bg-[#0d1117] text-[#c9d1d9] m-0 p-0 overflow-x-hidden`} style={{ fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji'" }}>
        {children}
      </body>
    </html>
  );
}
