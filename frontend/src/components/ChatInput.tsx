"use client";

import React, { useState } from "react";

interface ChatInputProps {
  onSend: (question: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ onSend, disabled = false, placeholder = "Ask anything about luxury properties..." }: ChatInputProps) {
  const [value, setValue] = useState("");
  const isDisabled = disabled || !value.trim();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed === "" || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  return (
    <div className="bg-white border border-neutral-200 rounded-2xl p-3 mb-4 max-w-[900px] min-w-0 w-full mx-auto shadow-sm">
      <form onSubmit={handleSubmit} className="flex items-end gap-2">
        <textarea
          aria-label="Ask a property question"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={3}
          className="flex-1 min-w-0 min-h-[48px] resize-none border-none bg-transparent focus:ring-0 text-sm text-neutral-800 placeholder:text-neutral-400"
          disabled={disabled}
          spellCheck={false}
          autoComplete="off"
        />
        <button
          type="submit"
          aria-label="Send message"
          disabled={isDisabled}
          className={`shrink-0 px-5 py-2.5 rounded-xl font-medium text-sm transition-colors flex items-center gap-2 ${
            isDisabled
              ? "bg-neutral-200 text-neutral-400 cursor-not-allowed"
              : "bg-teal-900 text-white hover:bg-teal-800 focus:ring-2 focus:ring-teal-900/30"
          }`}
        >
          {disabled ? (
            <span className="w-4 h-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-4 h-4"
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
          )}
        </button>
      </form>
    </div>
  );
}
