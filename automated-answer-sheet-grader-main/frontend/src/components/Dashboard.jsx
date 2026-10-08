import { useEffect, useState } from "react";
import { useApi } from "../lib/api";
import AccountPanel from "./AccountPanel";
import GradeForm from "./GradeForm";
import History from "./History";
import TeacherPanel from "./TeacherPanel";
import { Button } from "./ui";

export default function Dashboard({ token, username: initialName, onLogout }) {
  const apiFetch = useApi(token, onLogout);
  const [username, setUsername] = useState(initialName);
  const [isAdmin, setIsAdmin] = useState(false);
  const [page, setPage] = useState("grade");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    apiFetch("/auth/me")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d) {
          setUsername(d.username);
          setIsAdmin(Boolean(d.is_admin));
        }
      })
      .catch(() => {});
  }, [apiFetch]);

  return (
    <div className="min-h-screen bg-[var(--canvas)]">
      <header className="sticky top-0 z-10 border-b border-[var(--line)] bg-[var(--paper)]/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-800 text-lg text-white shadow-sm">✓</div>
            <div>
              <h1 className="text-lg font-semibold leading-tight text-slate-900">Answer Sheet Grader</h1>
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-emerald-800">Assessment office</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {username && (
              <span className="hidden items-center gap-2 rounded-full border border-[var(--line)] bg-white px-3 py-1.5 text-xs text-slate-600 sm:inline-flex">
                <span className="h-2 w-2 rounded-full bg-emerald-600" />
                <strong className="font-semibold text-slate-900">{username}</strong>
              </span>
            )}
            <Button variant="secondary" size="sm" onClick={onLogout}>Sign out</Button>
          </div>
        </div>
      </header>

      <nav className="mx-auto max-w-6xl px-4 pt-5 sm:px-6">
        <div className="inline-flex max-w-full gap-1 overflow-x-auto rounded-lg border border-[var(--line)] bg-[var(--paper)] p-1 shadow-sm">
          {[
            ["grade", "Grade"],
            ["history", "History"],
            ["account", "Account"],
            ...(isAdmin ? [["teacher", "Teacher accounts"]] : []),
          ].map(([id, label]) => (
            <button key={id} type="button" onClick={() => setPage(id)}
              className={`shrink-0 rounded-md px-3 py-2 text-sm font-medium transition-colors ${page === id
                ? "bg-emerald-800 text-white shadow-sm"
                : "text-slate-600 hover:bg-emerald-50 hover:text-emerald-900"}`}>
              {label}
            </button>
          ))}
        </div>
      </nav>

      <main className="surface-in mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        {page === "grade" && <GradeForm apiFetch={apiFetch}
          onSaved={() => setRefreshKey((key) => key + 1)} />}
        {page === "history" && <History apiFetch={apiFetch} refreshKey={refreshKey} />}
        {page === "account" && <AccountPanel apiFetch={apiFetch} />}
        {page === "teacher" && isAdmin && <TeacherPanel apiFetch={apiFetch} />}
      </main>
    </div>
  );
}
