"use client";

import React, { useState, useEffect, useCallback } from "react";
import { sendChat, ApiError } from "@/lib/api";
import { ChatMessage, ChatResponse } from "@/types";
import ChatMessageComponent from "./ChatMessage";
import { ChatInput, LoadingIndicator, ErrorIndicator } from "./ChatMessage";
import WelcomeScreen from "./WelcomeScreen";

interface ChatWindowProps {
  className?: string;
}

export default function ChatWindow({ className }: ChatWindowProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [welcomeShown, setWelcomeShown] = useState(true);
  const messagesEndRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (node) {
        node.scrollIntoView({ behavior: "smooth" });
      }
    },
    []
  );

  const handleSend = useCallback(
    async (question: string) => {
      setError(null);
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: question,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      try {
        const response: ChatResponse = await sendChat(question);
        const assistantMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.detail || "An error occurred. Please try again.");
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("An unexpected error occurred. Please try again.");
        }
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const handleRetry = useCallback(() => {
    const lastUserMessage = [...messages]
      .reverse()
      .find((m) => m.role === "user");
    if (lastUserMessage) {
      handleSend(lastUserMessage.content);
    }
    setError(null);
  }, [messages, handleSend]);

  const handleSuggestion = (question: string) => {
    setWelcomeShown(false);
    handleSend(question);
  };

  return (
    <div className={`flex flex-col h-full ${className || ""}`}>
      {welcomeShown && !isLoading && !error ? (
        <WelcomeScreen onAskQuestion={handleSuggestion} />
      ) : (
        <div className="flex-1 overflow-y-auto p-6 md:p-8">
          {messages.length === 0 && !isLoading && !error ? (
            <div className="flex flex-col h-full items-center justify-center text-center px-4">
              <p className="text-neutral-500 italic">
                Start a conversation by asking a question.
              </p>
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
          <ChatInput onSend={handleSend} disabled={isLoading} />
        </div>
      )}
    </div>
  );
}
