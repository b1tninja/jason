import type { ReactNode } from "react";

export function AppShell({ title, nav, children }: { title: string; nav?: ReactNode; children: ReactNode }) {
  return (
    <div className="shell">
      <header className="shell-bar">
        <a href="/" className="brand">
          {title}
        </a>
        {nav}
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}
