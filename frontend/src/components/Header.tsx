"use client";

import { MoreHorizontal } from "lucide-react";

interface HeaderProps {
  onMenuClick: () => void;
}

export default function Header({ onMenuClick }: HeaderProps) {
  return (
    <header className="sticky top-0 z-10 border-b border-neutral-200 bg-ivory-50/80 backdrop-blur">
      <div className="flex items-center justify-between px-6 py-3">
        <button
          onClick={onMenuClick}
          className="p-2 rounded-md hover:bg-neutral-100 text-neutral-600"
        >
          <span className="sr-only">Open menu</span>
          <MoreHorizontal className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-neutral-200 flex items-center justify-center text-neutral-600 text-sm font-medium">
            RA
          </div>
          <div className="flex items-center gap-2 pl-2 border-l border-neutral-200">
            <span className="text-sm font-medium text-neutral-700">RealtyAI</span>
          </div>
        </div>
      </div>
    </header>
  );
}
