"use client";

import React, { useEffect, useRef } from "react";
import { useConversation } from "@/components/ConversationContext";
import ChatMessageComponent from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { LoadingIndicator, ErrorIndicator } from "./ChatMessage";
import WelcomeScreen from "./WelcomeScreen";

interface ChatWindowProps {
  className?: string;
}

export default function ChatWindow({ className }: ChatWindowProps) {
  const {
    activeConversation,
    isHydrated,
    isLoading,
    error,
    handleSendMessage,
    handleRetry,
  } = useConversation();

  const messages = activeConversation?.messages || [];
  const welcomeShown = messages.length === 0;

  const messagesEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeConversation?.id, messages.length, isLoading, error]);

  return (
    <div className={`flex flex-col h-full min-h-0 min-w-0 ${className || ""}`}>
      <main className="flex-1 min-h-0 min-w-0 overflow-y-auto p-4 md:p-8">
        {welcomeShown ? (
          <div className="flex flex-col items-center justify-center h-full px-4">
            <WelcomeScreen onSelectQuestion={handleSendMessage} disabled={!isHydrated} />
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-4 mb-6">
              {messages.map((msg) => (
                <ChatMessageComponent key={msg.id} message={msg} />
              ))}
              {isLoading && (
                <LoadingIndicator message="Analyzing property data..." />
              )}
            </div>
            {error && <ErrorIndicator message={error} onRetry={handleRetry} />}
            <div ref={messagesEndRef} />
          </>
        )}
      </main>

      <ChatInput
        key={activeConversation?.id}
        onSend={handleSendMessage}
        disabled={isLoading || !isHydrated}
      />
    </div>
  );
}
