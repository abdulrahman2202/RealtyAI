"use client";

import { ChevronLeft, Plus, Building2 } from "lucide-react";

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  onNewConversation: () => void;
  activeConversationId: string | null;
  conversations: { id: string; title: string }[];
  onSelectConversation: (id: string) => void;
}

export default function Sidebar({
  isCollapsed,
  onToggle,
  onNewConversation,
  activeConversationId,
  conversations,
  onSelectConversation,
}: SidebarProps) {
  return (
    <aside
      className={`fixed inset-y-0 left-0 z-20 border-r border-neutral-200 bg-ivory-50 transition-all duration-300 ${
        isCollapsed ? "w-16" : "w-72"
      }`}
    >
      <div className="flex flex-col h-full">
        {/* Brand */}
        <div className="flex items-center gap-2 px-4 py-6 border-b border-neutral-200">
          <button onClick={onToggle} className="ml-2 mr-1 p-1.5 rounded-md hover:bg-neutral-100 text-neutral-600">
            <span className="sr-only">Toggle sidebar</span>
            <ChevronLeft className={`w-5 h-5 ${isCollapsed ? "rotate-180" : ""}`} />
          </button>
          <div className={`flex items-center gap-2 transition-opacity duration-300 ${isCollapsed ? "opacity-0" : "opacity-100"}`}>
            <div className="w-8 h-8 rounded bg-teal-900 flex items-center justify-center text-white">
              <Building2 className="w-5 h-5" />
            </div>
            <span className="text-xl font-serif font-bold tracking-tight text-teal-900">RealtyAI</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto">
          <div className={`flex items-center gap-2 px-2 py-2 rounded-lg transition-colors mb-4 ${!isCollapsed ? "bg-neutral-100" : ""}`}>
            <button onClick={onNewConversation} className="flex-1 flex items-center gap-2 text-sm font-medium text-neutral-700 hover:text-teal-900">
              <Plus className="w-4 h-4" />
              <span className={`hidden sm:inline ${isCollapsed ? "hidden" : "inline"}`}>New conversation</span>
            </button>
          </div>

          <div className="space-y-1 px-2">
            <p className={`px-3 py-2 text-xs font-medium text-neutral-500 ${isCollapsed ? "hidden" : "block"}`}>Recent</p>
            {conversations.length === 0 && !isCollapsed ? (
              <p className="px-4 py-4 text-sm text-neutral-400 text-center">No conversations yet</p>
            ) : (
              conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => onSelectConversation(conv.id)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                    activeConversationId === conv.id
                      ? "bg-teal-900/10 text-teal-900 border border-teal-900/20"
                      : "text-neutral-600 hover:bg-neutral-100"
                  }`}
                >
                  <Building2 className="w-4 h-4 text-neutral-400" />
                  <span className={`truncate ${isCollapsed ? "hidden" : "block"}`}>{conv.title}</span>
                </button>
              ))
            )}
          </div>
        </nav>
      </div>
    </aside>
  );
}
