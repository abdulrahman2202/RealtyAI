"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";

export default function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<{ id: string; title: string }[]>([]);

  return (
    <div>
      <Sidebar
        isCollapsed={isCollapsed}
        onToggle={() => setIsCollapsed((prev) => !prev)}
        onNewConversation={() => {
          const id = crypto.randomUUID();
          setConversations((prev) => [...prev, { id, title: "New conversation" }]);
          setActiveConversationId(id);
        }}
        activeConversationId={activeConversationId}
        conversations={conversations}
        onSelectConversation={setActiveConversationId}
      />
      <div className="flex flex-col h-screen overflow-hidden md:pl-16">
        <Header onMenuClick={() => setIsCollapsed((prev) => !prev)} />
        <main className="flex-1 overflow-hidden relative">{children}</main>
      </div>
    </div>
  );
}
