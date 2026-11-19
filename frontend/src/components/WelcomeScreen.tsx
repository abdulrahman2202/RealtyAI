"use client";

import { ArrowRight, Building2 } from "lucide-react";

interface SuggestionCardProps {
  question: string;
  onSelectQuestion: (q: string) => void;
  disabled?: boolean;
}

export function SuggestionCard({ question, onSelectQuestion, disabled }: SuggestionCardProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onSelectQuestion(question)}
      className="flex items-start gap-3 p-4 rounded-xl border border-neutral-200 bg-white text-left hover:border-teal-900/40 hover:bg-teal-50/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-900/20"
    >
      <div className="flex-shrink-0 w-9 h-9 rounded bg-neutral-100 flex items-center justify-center text-neutral-600 group-hover:bg-teal-900/10 group-hover:text-teal-900 transition-colors">
        <ArrowRight className="w-4 h-4" />
      </div>
      <span className="text-sm text-neutral-700 group-hover:text-teal-900 transition-colors leading-relaxed">
        {question}
      </span>
    </button>
  );
}

interface WelcomeScreenProps {
  onSelectQuestion: (question: string) => void;
  disabled?: boolean;
}

export default function WelcomeScreen({ onSelectQuestion, disabled }: WelcomeScreenProps) {
  const suggestions = [
    "Tell me about Albert Hall Mansions.",
    "What is Top Of the Astera?",
    "Show me DarGlobal properties in London.",
    "What information is available about the listed properties?",
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-8 animate-fade-in">
      <div className="flex items-center justify-center w-16 h-16 rounded-full bg-teal-900/10 mb-6 text-teal-900">
        <Building2 className="w-8 h-8" />
      </div>
      <h1 className="text-3xl font-serif font-bold text-teal-900 mb-2 tracking-tight">
        Discover properties with intelligence.
      </h1>
      <p className="text-lg text-neutral-600 max-w-xl mb-8 leading-relaxed">
        RealtyAI helps you explore luxury properties with AI-generated answers backed by verified source references.
      </p>

      <div className="w-full max-w-2xl space-y-3">
        <p className="text-xs font-semibold text-neutral-400 tracking-wider uppercase px-2 self-start">
          Suggested questions
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
          {suggestions.map((q, i) => (
            <SuggestionCard key={i} question={q} onSelectQuestion={onSelectQuestion} disabled={disabled} />
          ))}
        </div>
      </div>
    </div>
  );
}
