"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import { ConversationProvider } from "@/components/ConversationContext";
import { cn } from "@/lib/utils";

export default function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const checkWidth = () => {
      if (window.innerWidth >= 768) {
        setIsMobileMenuOpen(false);
      }
    };
    window.addEventListener("resize", checkWidth);
    return () => window.removeEventListener("resize", checkWidth);
  }, []);

  return (
    <ConversationProvider>
      <div className="flex h-screen min-w-0 overflow-hidden">
        {/* Sidebar: part of flex flow on desktop, fixed overlay on mobile */}
        <div
          className={cn(
            "h-full min-w-0 shrink-0 overflow-hidden bg-ivory-50 transition-all duration-300 md:static md:block",
            isCollapsed ? "w-16" : "w-72",
            isMobileMenuOpen ? "fixed inset-y-0 left-0 z-30" : "hidden"
          )}
        >
          <Sidebar
            isCollapsed={isCollapsed}
            onToggle={() => setIsCollapsed((prev) => !prev)}
          />
        </div>

        {/* Main content: flex-1, centered within remaining space */}
        <div className="flex flex-col flex-1 min-h-0 min-w-0 relative z-10">
          <Header
            onMenuClick={() => {
              if (typeof window !== "undefined" && window.innerWidth < 768) {
                setIsMobileMenuOpen((prev) => !prev);
              } else {
                setIsCollapsed((prev) => !prev);
              }
            }}
          />
          <main className="flex-1 min-h-0 min-w-0 overflow-hidden relative">{children}</main>
        </div>
      </div>
    </ConversationProvider>
  );
}
