import { useState } from "react";
import { readError } from "../lib/api";
import { Alert, Button, Card, Field, Input } from "./ui";

export default function AccountPanel({ apiFetch }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
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

  async function run(action, success) {
    setMessage("");
    setProblem("");
    try {
      await action();
      setMessage(success);
    } catch (err) {
      setProblem(err.message);
    }
  }

  return (
    <Card title="Personal account" subtitle="Manage your password">
      <div className="max-w-lg">
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            run(async () => {
              await call("/auth/change-password", {
                current_password: current,
                new_password: next,
              });
              setCurrent("");
              setNext("");
            }, "Password changed.");
          }}
        >
          <h3 className="text-sm font-semibold text-slate-900">Change password</h3>
          <Field label="Current password">
            <Input type="password" value={current} autoComplete="current-password"
              onChange={(e) => setCurrent(e.target.value)} required />
          </Field>
          <Field label="New password" hint="At least 8 characters">
            <Input type="password" value={next} autoComplete="new-password" minLength={8}
              onChange={(e) => setNext(e.target.value)} required />
          </Field>
          <Button type="submit">Change password</Button>
        </form>
      </div>

      {(message || problem) && (
        <div className="mt-5">
          {message && <Alert tone="success">{message}</Alert>}
          {problem && <Alert tone="error">{problem}</Alert>}
        </div>
      )}
    </Card>
  );
}
