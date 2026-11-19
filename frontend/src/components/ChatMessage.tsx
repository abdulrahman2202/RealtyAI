"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Source } from "@/types";

interface ChatMessageProps {
  message: {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources?: Source[];
    timestamp: Date;
  };
}

function renderMarkdownContent(content: string) {
  return (
    <div className="chat-markdown text-neutral-800 leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const time = message.timestamp.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  const renderContent = isUser ? (
    <p className="leading-relaxed whitespace-pre-line text-white">{message.content}</p>
  ) : (
    renderMarkdownContent(message.content)
  );

  return (
    <div
      className={`flex w-full flex-col ${
        isUser ? "items-end" : "items-start"
      } animate-slide-up`}
    >
      <div
        className={`min-w-0 max-w-[85%] break-words px-4 py-3 rounded-2xl ${
          isUser
            ? "bg-teal-900 text-white rounded-tr-none"
            : "bg-white text-neutral-800 border border-neutral-200 rounded-tl-none"
        }`}
      >
        {renderContent}
      </div>

      {message.role === "assistant" && message.sources && message.sources.length > 0 && (
        <div className="mt-2 max-w-[85%] min-w-0 px-4 flex flex-col gap-2">
          <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">
            Sources
          </p>
          <div className="flex flex-wrap gap-2">
            {message.sources.map((source, i) => (
              <div key={i} className="min-w-0 break-words px-2 py-1 rounded-md bg-ivory-100 border border-neutral-200">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-teal-900 hover:text-orange-accent hover:underline transition-colors"
                >
                  {source.title}
                </a>
              </div>
            ))}
          </div>
        </div>
      )}

      <span className={`mt-1 text-xs text-neutral-600 ${isUser ? "ml-auto" : ""}`}>
        {time}
      </span>
    </div>
  );
}

interface LoadingIndicatorProps {
  message?: string;
}

export function LoadingIndicator({ message = "Thinking..." }: LoadingIndicatorProps) {
  return (
    <div className="flex items-start gap-3 px-4 py-3 animate-slide-up">
      <div className="flex-shrink-0 w-8 h-8 rounded bg-teal-900/10 flex items-center justify-center text-teal-900 mt-1">
        <Loader2 className="w-4 h-4 animate-spin" />
      </div>
      <div>
        <p className="text-sm text-neutral-600">{message}</p>
      </div>
    </div>
  );
}

interface ErrorIndicatorProps {
  message: string;
  onRetry: () => void;
}

export function ErrorIndicator({ message, onRetry }: ErrorIndicatorProps) {
  return (
    <div role="alert" className="flex items-center gap-3 px-4 py-3 animate-slide-up">
      <div className="flex-shrink-0 w-8 h-8 rounded bg-orange-accent/10 flex items-center justify-center text-orange-accent">
        <Send className="w-4 h-4" />
      </div>
      <div className="flex-1">
        <p className="text-sm text-neutral-800">{message}</p>
        <button
          onClick={onRetry}
          className="mt-2 text-xs text-teal-900 hover:underline font-medium"
        >
          Try again
        </button>
      </div>
    </div>
  );
}

function Send({ className = "" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={`w-4 h-4 ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function Loader2({ className = "" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className={`w-4 h-4 ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}
