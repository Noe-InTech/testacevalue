"use client";

import { useState, type ReactNode } from "react";

interface CollapsibleSectionProps {
  title: string;
  badge?: number | string;
  defaultOpen?: boolean;
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
  search,
  children,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="panel collapsible">
      <button
        type="button"
        className="collapsible-trigger"
        onClick={() => setOpen((value) => !value)}
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
