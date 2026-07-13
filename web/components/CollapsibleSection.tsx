"use client";

import { useState, type ReactNode } from "react";

interface CollapsibleSectionProps {
  title: string;
  badge?: number | string;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  search?: {
    value: string;
    onChange: (value: string) => void;
    placeholder: string;
  };
  children: ReactNode;
}

export function CollapsibleSection({
  title,
  badge,
  defaultOpen = false,
  open: controlledOpen,
  onOpenChange,
  search,
  children,
}: CollapsibleSectionProps) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const open = controlledOpen ?? internalOpen;

  const toggle = () => {
    const next = !open;
    if (onOpenChange) {
      onOpenChange(next);
    } else {
      setInternalOpen(next);
    }
  };

  return (
    <section className="panel collapsible">
      <button
        type="button"
        className="collapsible-trigger"
        onClick={toggle}
        aria-expanded={open}
      >
        <span className="collapsible-title">{title}</span>
        {badge !== undefined ? <span className="badge">{badge}</span> : null}
        <span className="collapsible-chevron">{open ? "▾" : "▸"}</span>
      </button>
      {open ? (
        <div className="collapsible-body">
          {search ? (
            <label className="section-search">
              Rechercher
              <input
                type="search"
                value={search.value}
                onChange={(event) => search.onChange(event.target.value)}
                placeholder={search.placeholder}
              />
            </label>
          ) : null}
          {children}
        </div>
      ) : null}
    </section>
  );
}
