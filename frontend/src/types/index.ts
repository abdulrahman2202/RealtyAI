export interface Source {
  title: string;
  url: string;
}

export interface ChatRequest {
  question: string;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  success: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  timestamp: Date;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: Date;
  updatedAt: Date;
}
