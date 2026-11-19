import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import SidebarProvider from "@/components/SidebarProvider";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });

export const metadata: Metadata = {
  title: "RealtyAI — Real Estate Intelligence",
  description: "Ask about luxury properties. Get AI-generated answers with verified source references.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} font-sans antialiased`}>
      <head>
        <link
          rel="icon"
          href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2312544f' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M22 12c0-4.97-4.03-9-9-9s-9 4.03-9 9 4.03 9 9 9 9-4.03 9-9Z'/%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3C/svg%3E"
        />
      </head>
      <body className="bg-ivory-50 text-neutral-900">
        <SidebarProvider>{children}</SidebarProvider>
      </body>
    </html>
  );
}
