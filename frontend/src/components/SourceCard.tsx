"use client";

import { ArrowRight, Building2, MapPin } from "lucide-react";
import { Source } from "@/types";

interface SourceCardProps {
  source: Source;
}

export default function SourceCard({ source }: SourceCardProps) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-3 p-3 rounded-lg border border-neutral-200 bg-white hover:border-teal-900/30 transition-colors group"
    >
      <div className="flex-shrink-0 w-8 h-8 rounded bg-teal-900/10 flex items-center justify-center text-teal-900">
        <Building2 className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-medium text-neutral-800 truncate group-hover:text-teal-900 transition-colors">
          {source.title}
        </h4>
        <div className="flex items-center gap-1 mt-1">
          <MapPin className="w-3 h-3 text-neutral-400" />
          <span className="text-xs text-neutral-500 truncate">{source.url}</span>
        </div>
      </div>
      <ArrowRight className="w-4 h-4 text-neutral-400 group-hover:text-teal-900 transition-colors flex-shrink-0" />
    </a>
  );
}
