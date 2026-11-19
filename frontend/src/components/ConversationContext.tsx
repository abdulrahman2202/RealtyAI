"use client";

import React, { createContext, useContext, useReducer, useRef, useEffect, useCallback } from "react";
import { Conversation, ChatMessage } from "@/types";
import { sendChat } from "@/lib/api";

const CONVERSATIONS_STORAGE_KEY = "realtyai_conversations";
const ACTIVE_CONVERSATION_STORAGE_KEY = "realtyai_active_conversation";

interface RequestState {
  requestId: string;
  userMessageId: string;
  isLoading: boolean;
  error: string | null;
}

interface ConversationState {
  conversations: Conversation[];
  activeConversationId: string | null;
  requests: Record<string, RequestState>;
  isHydrated: boolean;
}

type Action =
  | { type: "restore"; conversations: Conversation[]; activeConversationId: string }
  | { type: "new"; conversation: Conversation }
  | { type: "select"; conversationId: string }
  | { type: "delete"; conversationId: string }
  | { type: "submit"; conversationId: string; userMessage: ChatMessage; requestId: string }
  | { type: "retry"; conversationId: string; userMessageId: string; requestId: string }
  | { type: "answer"; conversationId: string; requestId: string; message: ChatMessage }
  | { type: "error"; conversationId: string; requestId: string; error: string };

function newConversation(id: string, now: Date): Conversation {
  return { id, title: "New conversation", messages: [], createdAt: now, updatedAt: now };
}

function conversationReducer(state: ConversationState, action: Action): ConversationState {
  switch (action.type) {
    case "restore":
      return state.isHydrated ? state : {
        ...state,
        conversations: action.conversations,
        activeConversationId: action.activeConversationId,
        isHydrated: true,
      };
    case "new":
      return {
        ...state,
        conversations: [...state.conversations, action.conversation],
        activeConversationId: action.conversation.id,
      };
    case "select":
      return state.conversations.some(c => c.id === action.conversationId)
        ? { ...state, activeConversationId: action.conversationId }
        : state;
    case "delete": {
      if (!state.conversations.some(c => c.id === action.conversationId)) return state;
      const conversations = state.conversations.filter(c => c.id !== action.conversationId);
      const requests = { ...state.requests };
      delete requests[action.conversationId];
      return {
        ...state,
        conversations,
        requests,
        activeConversationId: state.activeConversationId === action.conversationId
          ? conversations[0]?.id || null
          : state.activeConversationId,
      };
    }
    case "submit": {
      const existing = state.conversations.find(c => c.id === action.conversationId);
      const conversation = existing || newConversation(action.conversationId, action.userMessage.timestamp);
      const updated = {
        ...conversation,
        title: conversation.messages.length === 0 ? action.userMessage.content : conversation.title,
        messages: [...conversation.messages, action.userMessage],
        updatedAt: action.userMessage.timestamp,
      };
      return {
        ...state,
        conversations: existing
          ? state.conversations.map(c => c.id === action.conversationId ? updated : c)
          : [...state.conversations, updated],
        activeConversationId: action.conversationId,
        requests: {
          ...state.requests,
          [action.conversationId]: {
            requestId: action.requestId,
            userMessageId: action.userMessage.id,
            isLoading: true,
            error: null,
          },
        },
      };
    }
    case "retry":
      return {
        ...state,
        requests: {
          ...state.requests,
          [action.conversationId]: {
            requestId: action.requestId,
            userMessageId: action.userMessageId,
            isLoading: true,
            error: null,
          },
        },
      };
    case "answer":
    case "error": {
      const request = state.requests[action.conversationId];
      if (!request || request.requestId !== action.requestId) return state;
      return {
        ...state,
        conversations: action.type === "answer"
          ? state.conversations.map(c => c.id === action.conversationId ? {
              ...c,
              messages: [...c.messages, action.message],
              updatedAt: action.message.timestamp,
            } : c)
          : state.conversations,
        requests: {
          ...state.requests,
          [action.conversationId]: {
            ...request,
            isLoading: false,
            error: action.type === "error" ? action.error : null,
          },
        },
      };
    }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

// Keep the existing storage format, while recovering safely from invalid history.
function restoreConversations(stored: string | null): Conversation[] {
  const parsed: unknown = stored ? JSON.parse(stored) : [];
  if (!Array.isArray(parsed)) return [];
  return parsed.flatMap((value: unknown): Conversation[] => {
    if (!isRecord(value) || typeof value.id !== "string" || !value.id ||
        typeof value.title !== "string" || !Array.isArray(value.messages)) return [];
    const createdAt = new Date(String(value.createdAt));
    const updatedAt = new Date(String(value.updatedAt));
    if (!Number.isFinite(createdAt.getTime()) || !Number.isFinite(updatedAt.getTime())) return [];
    const messages: ChatMessage[] = [];
    for (const message of value.messages) {
      if (!isRecord(message) || typeof message.id !== "string" ||
          (message.role !== "user" && message.role !== "assistant") ||
          typeof message.content !== "string") return [];
      const timestamp = new Date(String(message.timestamp));
      if (!Number.isFinite(timestamp.getTime())) return [];
      const sources = Array.isArray(message.sources)
        ? message.sources.filter(isRecord).flatMap(source =>
            typeof source.title === "string" && typeof source.url === "string"
              ? [{ title: source.title, url: source.url }] : [])
        : undefined;
      messages.push({ id: message.id, role: message.role, content: message.content, timestamp, sources });
    }
    return [{ id: value.id, title: value.title, createdAt, updatedAt, messages }];
  });
}

interface ConversationContextType {
  conversations: Conversation[];
  activeConversationId: string | null;
  activeConversation: Conversation | null;
  isHydrated: boolean;
  isLoading: boolean;
  error: string | null;
  handleNewConversation: () => void;
  handleSelectConversation: (id: string) => void;
  handleDeleteConversation: (id: string) => void;
  handleSendMessage: (question: string) => Promise<void>;
  handleRetry: () => Promise<void>;
}

const ConversationContext = createContext<ConversationContextType | null>(null);

export function ConversationProvider({ children }: { children: React.ReactNode }) {
  // Conversation history, selection and request status change together in one reducer.
  const [state, dispatch] = useReducer(conversationReducer, {
    conversations: [], activeConversationId: null, requests: {}, isHydrated: false,
  });
  // Event refs capture selection and prevent duplicate requests before React renders.
  const selectedId = useRef<string | null>(null);
  const inFlight = useRef(new Set<string>());
  const restored = useRef(false);

  useEffect(() => {
    if (restored.current) return;
    restored.current = true;
    let conversations: Conversation[] = [];
    let storedActiveId: string | null = null;
    try {
      conversations = restoreConversations(localStorage.getItem(CONVERSATIONS_STORAGE_KEY));
      storedActiveId = localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY);
    } catch {
      // Browsers can deny storage; in-memory conversations still work.
    }
    if (conversations.length === 0) {
      conversations = [newConversation(crypto.randomUUID(), new Date())];
    }
    const activeConversationId = conversations.find(c => c.id === storedActiveId)?.id || conversations[0].id;
    selectedId.current = activeConversationId;
    dispatch({ type: "restore", conversations, activeConversationId });
  }, []);

  useEffect(() => {
    // Never overwrite stored history with the pre-hydration empty array.
    if (!state.isHydrated) return;
    try {
      localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(state.conversations));
      if (state.activeConversationId) {
        localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, state.activeConversationId);
      } else {
        localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY);
      }
    } catch {
      // Storage being unavailable must not prevent chat submission.
    }
  }, [state.conversations, state.activeConversationId, state.isHydrated]);

  const handleNewConversation = useCallback(() => {
    if (!state.isHydrated) return;
    const conversation = newConversation(crypto.randomUUID(), new Date());
    selectedId.current = conversation.id;
    dispatch({ type: "new", conversation });
  }, [state.isHydrated]);

  const handleSelectConversation = useCallback((id: string) => {
    if (!state.conversations.some(c => c.id === id)) return;
    selectedId.current = id;
    dispatch({ type: "select", conversationId: id });
  }, [state.conversations]);

  const handleDeleteConversation = useCallback((id: string) => {
    const action: Action = { type: "delete", conversationId: id };
    const nextState = conversationReducer(state, action);
    if (nextState === state) return;
    selectedId.current = nextState.activeConversationId;
    dispatch(action);
    // Save the confirmed deletion immediately, before the next React render.
    try {
      localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(nextState.conversations));
      if (nextState.activeConversationId) {
        localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, nextState.activeConversationId);
      } else {
        localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY);
      }
    } catch {
      // The in-memory deletion still works when browser storage is unavailable.
    }
  }, [state]);

  const requestAnswer = useCallback(async (conversationId: string, requestId: string, question: string) => {
    try {
      const response = await sendChat(question);
      dispatch({
        type: "answer", conversationId, requestId,
        message: {
          id: crypto.randomUUID(), role: "assistant", content: response.answer,
          sources: response.sources, timestamp: new Date(),
        },
      });
    } catch (error) {
      dispatch({
        type: "error", conversationId, requestId,
        error: error instanceof Error ? error.message : "An unexpected error occurred. Please try again.",
      });
    } finally {
      inFlight.current.delete(conversationId);
    }
  }, []);

  const handleSendMessage = useCallback(async (input: string) => {
    const question = input.trim();
    if (!question || !state.isHydrated) return;
    // Capture once: React's next selection is never read after dispatching.
    const conversationId = selectedId.current || crypto.randomUUID();
    if (inFlight.current.has(conversationId)) return;
    selectedId.current = conversationId;
    inFlight.current.add(conversationId);
    const requestId = crypto.randomUUID();
    dispatch({
      type: "submit", conversationId, requestId,
      userMessage: { id: crypto.randomUUID(), role: "user", content: question, timestamp: new Date() },
    });
    await requestAnswer(conversationId, requestId, question);
  }, [state.isHydrated, requestAnswer]);

  const handleRetry = useCallback(async () => {
    const conversationId = selectedId.current;
    if (!conversationId || inFlight.current.has(conversationId)) return;
    const request = state.requests[conversationId];
    const userMessage = state.conversations.find(c => c.id === conversationId)?.messages
      .find(m => m.id === request?.userMessageId && m.role === "user");
    if (!request?.error || !userMessage) return;
    const requestId = crypto.randomUUID();
    inFlight.current.add(conversationId);
    dispatch({ type: "retry", conversationId, requestId, userMessageId: userMessage.id });
    await requestAnswer(conversationId, requestId, userMessage.content);
  }, [state.requests, state.conversations, requestAnswer]);

  const activeConversation = state.conversations.find(c => c.id === state.activeConversationId) || null;
  const activeRequest = state.activeConversationId ? state.requests[state.activeConversationId] : undefined;
  const value: ConversationContextType = {
    conversations: state.conversations,
    activeConversationId: state.activeConversationId,
    activeConversation,
    isHydrated: state.isHydrated,
    isLoading: activeRequest?.isLoading || false,
    error: activeRequest?.error || null,
    handleNewConversation, handleSelectConversation, handleDeleteConversation, handleSendMessage, handleRetry,
  };

  return <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>;
}

export function useConversation() {
  const context = useContext(ConversationContext);
  if (!context) throw new Error("useConversation must be used within a ConversationProvider");
  return context;
}
