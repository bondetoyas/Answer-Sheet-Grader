import { useEffect, useState } from "react";
import { readError } from "../lib/api";
import { Alert, Badge, Button, Card, Field, Input } from "./ui";

export default function TeacherPanel({ apiFetch }) {
  const [users, setUsers] = useState([]);
  const [newUser, setNewUser] = useState({ username: "", password: "", is_admin: false });
  const [message, setMessage] = useState("");
  const [problem, setProblem] = useState("");

  async function call(path, body) {
    const response = await apiFetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(await readError(response, "Request failed."));
    return response.json();
  }

  async function loadUsers() {
    const response = await apiFetch("/admin/users");
    if (!response.ok) throw new Error(await readError(response, "Could not load teacher accounts."));
    setUsers(await response.json());
  }

  useEffect(() => {
    loadUsers().catch((error) => setProblem(error.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run(action, success) {
    setMessage("");
    setProblem("");
    try {
      await action();
      setMessage(success);
    } catch (error) {
      setProblem(error.message);
    }
  }

  return (
    <Card title="Teacher accounts" subtitle="Create accounts and reset teacher passwords">
      <div className="space-y-5">
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
          {users.map((user) => (
            <li key={user.id} className="flex flex-wrap items-center justify-between gap-3 px-3 py-2.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-900">{user.username}</p>
                <p className="text-xs text-slate-500">{user.submissions} saved grades</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={user.is_admin ? "indigo" : "slate"}>
                  {user.is_admin ? "Admin" : "Teacher"}
                </Badge>
                <Button size="sm" variant="secondary" onClick={() => {
                  const password = window.prompt(`New password for ${user.username} (min 8 characters)`);
                  if (password) run(() => call(`/admin/users/${user.id}/reset-password`, {
                    new_password: password,
                  }), `Password reset for ${user.username}.`);
                }}>
                  Reset password
                </Button>
              </div>
            </li>
          ))}
        </ul>

        <form className="space-y-4 rounded-lg bg-slate-50 p-4" onSubmit={(event) => {
          event.preventDefault();
          run(async () => {
            await call("/admin/users", newUser);
            setNewUser({ username: "", password: "", is_admin: false });
            await loadUsers();
          }, "Teacher account created.");
        }}>
          <h3 className="text-sm font-semibold text-slate-900">Add teacher</h3>
          <Field label="Username">
            <Input value={newUser.username} required
              onChange={(event) => setNewUser({ ...newUser, username: event.target.value })} />
          </Field>
          <Field label="Temporary password" hint="At least 8 characters">
            <Input type="password" value={newUser.password} minLength={8} required
              onChange={(event) => setNewUser({ ...newUser, password: event.target.value })} />
          </Field>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={newUser.is_admin}
              className="h-4 w-4 rounded border-slate-300 text-emerald-700 focus:ring-emerald-500"
              onChange={(event) => setNewUser({ ...newUser, is_admin: event.target.checked })} />
            Administrator
          </label>
          <Button type="submit">Create account</Button>
        </form>
        {message && <Alert tone="success">{message}</Alert>}
        {problem && <Alert tone="error">{problem}</Alert>}
      </div>
    </Card>
  );
}