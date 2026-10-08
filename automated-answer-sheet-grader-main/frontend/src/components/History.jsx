import { useCallback, useEffect, useState } from "react";
import { readError } from "../lib/api";
import { Alert, Button, Card } from "./ui";

export default function History({ apiFetch, refreshKey }) {
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const fetchAll = useCallback(async () => {
    try {
      const response = await apiFetch("/submissions");
      if (!response.ok) throw new Error("Could not load saved submissions.");
      setSubmissions(await response.json());
    } catch (err) {
      setError(err.message);
    }
  }, [apiFetch]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll, refreshKey]);

  async function refresh() {
    setLoading(true);
    setError("");
    await fetchAll();
    setLoading(false);
  }

  async function viewScan(imagePath) {
    try {
      const response = await apiFetch(imagePath);
      if (!response.ok) throw new Error("Could not load the scan.");
      const url = URL.createObjectURL(await response.blob());
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      setError(err.message);
    }
  }

  async function change(path, options, fallback) {
    setError("");
    setNotice("");
    try {
      const response = await apiFetch(path, options);
      if (!response.ok) throw new Error(await readError(response, fallback));
      setNotice((await response.json()).message);
      fetchAll();
    } catch (err) {
      setError(err.message);
    }
  }

  function editScore(submission) {
    const value = window.prompt(
      `Enter the new final score. Maximum: ${submission.max_marks}`,
      submission.final_score
    );
    if (value === null) return;
    change(`/submissions/${submission.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ final_score: Number(value) }),
    }, "Could not update the score.");
  }

  function remove(id) {
    if (!window.confirm("Delete this saved grade? This cannot be undone.")) return;
    change(`/submissions/${id}`, { method: "DELETE" }, "Could not delete the submission.");
  }

  return (
    <Card title="Saved submissions" subtitle="Grades you have approved"
      action={<Button variant="secondary" size="sm" onClick={refresh} disabled={loading}>
        {loading ? "Loading…" : "Refresh"}
      </Button>}>
      <div className="space-y-3">
        {error && <Alert tone="error">{error}</Alert>}
        {notice && <Alert tone="success">{notice}</Alert>}
      </div>

      {submissions.length === 0 ? (
        <p className="rounded-lg bg-slate-50 py-8 text-center text-sm text-slate-500">
          No saved grades yet.
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Student</th>
                <th className="px-4 py-3">Question</th>
                <th className="px-4 py-3 text-right">AI score</th>
                <th className="px-4 py-3 text-right">Final score</th>
                <th className="px-4 py-3 text-right">Maximum</th>
                <th className="px-4 py-3">Answer sheet</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {submissions.map((s) => (
                <tr key={s.id} className="hover:bg-slate-50">
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">{s.student_name}</td>
                  <td className="px-4 py-3 text-slate-600">{s.question_title}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{s.ai_score}</td>
                  <td className="px-4 py-3 text-right font-semibold text-slate-900">{s.final_score}</td>
                  <td className="px-4 py-3 text-right text-slate-600">{s.max_marks}</td>
                  <td className="px-4 py-3">
                    {s.image_path ? (
                      <Button size="sm" variant="secondary" onClick={() => viewScan(s.image_path)}>View scan</Button>
                    ) : (
                      <span className="text-slate-400">No image</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <div className="flex gap-2">
                      <Button size="sm" variant="secondary" onClick={() => editScore(s)}>Edit score</Button>
                      <Button size="sm" variant="danger" onClick={() => remove(s.id)}>Delete</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
