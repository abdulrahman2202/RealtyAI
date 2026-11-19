"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, Plus, Building2, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useConversation } from "@/components/ConversationContext";
import { Conversation } from "@/types";

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
}

export default function Sidebar({ isCollapsed, onToggle }: SidebarProps) {
  const {
    conversations,
    isHydrated,
    activeConversationId,
    handleNewConversation,
    handleSelectConversation,
    handleDeleteConversation,
  } = useConversation();
  const [pendingDelete, setPendingDelete] = useState<Conversation | null>(null);
  const deleteDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (pendingDelete && !deleteDialog.current?.open) deleteDialog.current?.showModal();
  }, [pendingDelete]);

  return (
    <aside
      className={cn(
        "h-full min-w-0 overflow-hidden border-r border-neutral-200 bg-ivory-50 transition-all duration-300 shrink-0",
        isCollapsed ? "w-16" : "w-72"
      )}
    >
      <div className="flex flex-col h-full min-h-0 min-w-0 overflow-hidden">
        {/* Brand */}
        <div className={`flex shrink-0 items-center gap-2 py-6 border-b border-neutral-200 ${isCollapsed ? "justify-center px-2" : "px-4"}`}>
          <button onClick={onToggle} className="shrink-0 p-1.5 rounded-md hover:bg-neutral-100 text-neutral-600">
            <span className="sr-only">Toggle sidebar</span>
            <ChevronLeft className={`w-5 h-5 ${isCollapsed ? "rotate-180" : ""}`} />
          </button>
          <div className={`items-center gap-2 min-w-0 overflow-hidden ${isCollapsed ? "hidden" : "flex"}`}>
            <div className="w-8 h-8 shrink-0 rounded bg-teal-900 flex items-center justify-center text-white">
              <Building2 className="w-5 h-5" />
            </div>
            <span className="min-w-0 truncate text-xl font-serif font-bold tracking-tight text-teal-900">RealtyAI</span>
          </div>
        </div>

        {/* Navigation */}
        <nav aria-label="Conversation history" className={`flex-1 min-h-0 min-w-0 py-4 overflow-x-hidden overflow-y-auto ${isCollapsed ? "px-2" : "px-3"}`}>
          <button
            type="button"
            onClick={handleNewConversation}
            disabled={!isHydrated}
            aria-label="New conversation"
            title="New conversation"
            className={`flex w-full min-w-0 h-10 items-center gap-2 rounded-lg mb-4 text-sm font-medium text-neutral-700 hover:text-teal-900 transition-colors ${isCollapsed ? "justify-center" : "px-3 bg-neutral-100"}`}
          >
            <Plus className="w-4 h-4 shrink-0" />
            <span className={isCollapsed ? "sr-only" : "min-w-0 truncate text-ellipsis"}>New conversation</span>
          </button>

          <div className="min-w-0 space-y-1">
            <p className={`px-3 py-2 text-xs font-medium text-neutral-500 ${isCollapsed ? "hidden" : "block"}`}>Recent</p>
            {conversations.length === 0 && !isCollapsed ? (
              <p className="px-4 py-4 text-sm text-neutral-400 text-center">No conversations yet</p>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={`group flex w-full min-w-0 h-10 overflow-hidden items-center rounded-lg border text-left text-sm transition-colors ${
                    activeConversationId === conv.id
                      ? "bg-teal-900/10 text-teal-900 border border-teal-900/20"
                      : "border-transparent text-neutral-600 hover:bg-neutral-100"
                  }`}
                >
                  <button
                    type="button"
                    title={conv.title}
                    aria-label={conv.title}
                    aria-current={activeConversationId === conv.id ? "page" : undefined}
                    onClick={() => handleSelectConversation(conv.id)}
                    className={`flex flex-1 min-w-0 h-full overflow-hidden items-center gap-3 text-left ${isCollapsed ? "justify-center" : "pl-3 pr-1"}`}
                  >
                    <Building2 className="w-4 h-4 shrink-0 text-neutral-600" />
                    <span className={`min-w-0 flex-1 truncate text-ellipsis ${isCollapsed ? "hidden" : "block"}`}>{conv.title}</span>
                  </button>
                  <button
                    type="button"
                    title={`Delete conversation: ${conv.title}`}
                    aria-label={`Delete conversation: ${conv.title}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      setPendingDelete(conv);
                    }}
                    className={`mr-1 flex h-7 shrink-0 items-center justify-center rounded-md text-neutral-600 hover:bg-neutral-100 hover:text-teal-900 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 [@media(hover:none)]:opacity-100 transition-opacity ${isCollapsed ? "w-6" : "w-7"}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))
            )}
          </div>
        </nav>
      </div>
      <dialog
        ref={deleteDialog}
        aria-labelledby="delete-conversation-title"
        aria-describedby="delete-conversation-description"
        onClose={() => setPendingDelete(null)}
        className="w-[calc(100%-2rem)] max-w-sm rounded-xl border border-neutral-200 bg-ivory-50 p-5 text-neutral-800 shadow-xl backdrop:bg-neutral-900/20"
      >
        <h2 id="delete-conversation-title" className="text-lg font-serif font-semibold text-teal-900">
          Delete conversation?
        </h2>
        <p id="delete-conversation-description" className="mt-2 text-sm break-words">
          Delete &ldquo;{pendingDelete?.title}&rdquo;? This cannot be undone.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            autoFocus
            onClick={() => deleteDialog.current?.close()}
            className="rounded-lg border border-neutral-200 px-3 py-2 text-sm hover:bg-neutral-100"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              if (pendingDelete) handleDeleteConversation(pendingDelete.id);
              deleteDialog.current?.close();
            }}
            className="rounded-lg bg-teal-900 px-3 py-2 text-sm text-white hover:bg-teal-800"
          >
            Delete
          </button>
        </div>
      </dialog>
    </aside>
  );
}
