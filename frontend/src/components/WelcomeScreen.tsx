"use client";

import { ArrowRight, Building2 } from "lucide-react";

interface SuggestionCardProps {
  question: string;
  onSelect: (q: string) => void;
}

export function SuggestionCard({ question, onSelect }: SuggestionCardProps) {
  return (
    <button
      onClick={() => onSelect(question)}
      className="w-full flex items-start gap-3 p-4 rounded-xl border border-neutral-200 bg-white text-left hover:border-teal-900/40 hover:bg-teal-50/50 transition-colors group"
    >
      <div className="flex-shrink-0 w-9 h-9 rounded bg-neutral-100 flex items-center justify-center text-neutral-600">
        <ArrowRight className="w-4 h-4" />
      </div>
      <span className="text-sm text-neutral-700 group-hover:text-teal-900 transition-colors leading-relaxed">
        {question}
      </span>
    </button>
  );
}

interface WelcomeScreenProps {
  onAskQuestion: (question: string) => void;
}

export default function WelcomeScreen({ onAskQuestion }: WelcomeScreenProps) {
  const suggestions = [
    "Tell me about Albert Hall Mansions.",
    "What is Top of the Astera?",
    "Show me DarGlobal properties in London.",
    "What properties are available on request?",
  ];

  return (
    <div className="flex flex-col h-full items-center justify-center text-center px-8 animate-fade-in">
      <div className="flex items-center justify-center w-16 h-16 rounded-full bg-teal-900/10 mb-6 text-teal-900">
        <Building2 className="w-8 h-8" />
      </div>
      <h1 className="text-3xl font-serif font-bold text-teal-900 mb-2">RealtyAI</h1>
      <p className="text-lg text-neutral-600 max-w-xl mb-8">
        Ask about luxury properties. Get AI-generated answers with verified source references.
      </p>

      <div className="w-full max-w-2xl space-y-3">
        <p className="text-xs font-semibold text-neutral-400 tracking-wider uppercase px-2">
          Suggested questions
        </p>
        {suggestions.map((q, i) => (
          <SuggestionCard key={i} question={q} onSelect={onAskQuestion} />
        ))}
      </div>
    </div>
  );
}
