import { useEffect, useRef, useState } from "react";
import { readError } from "../lib/api";
import { generateRubricFromAnswer, parseRubric } from "../lib/rubric";
import { Alert, Badge, Button, Card, Field, Input, Select, Textarea } from "./ui";

const RUBRIC_PLACEHOLDER = `Uses sunlight | sunlight | Plants use sunlight for photosynthesis. | 1
Uses water | water | Plants need water during photosynthesis. | 1
Uses carbon dioxide | carbon dioxide, carbon | Plants use carbon dioxide from air. | 1
Produces glucose or food | glucose, food | Plants make glucose or food. | 1
Releases oxygen | oxygen | Oxygen is released during photosynthesis. | 1`;

export default function GradeForm({ apiFetch, onSaved }) {
  const [studentName, setStudentName] = useState("");
  const [questionTitle, setQuestionTitle] = useState("");
  const [modelAnswer, setModelAnswer] = useState("");
  const [studentAnswer, setStudentAnswer] = useState("");
  const [rubricText, setRubricText] = useState("");
  const [totalMarks, setTotalMarks] = useState("5");
  const [modelAnswerFileName, setModelAnswerFileName] = useState("");
  const [modelImageLoading, setModelImageLoading] = useState(false);

  const [ocrFile, setOcrFile] = useState(null);
  const [imagePreview, setImagePreview] = useState("");
  const [storedImagePath, setStoredImagePath] = useState("");
  const [sections, setSections] = useState([]);
  const [ocrLoading, setOcrLoading] = useState(false);

  const [result, setResult] = useState(null);
  const [rubricItems, setRubricItems] = useState([]);
  const [finalScore, setFinalScore] = useState("");
  const [grading, setGrading] = useState(false);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");

  // Keep one object URL for the preview and release it when replaced/unmounted.
  const previewUrl = useRef("");
  useEffect(() => () => {
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
  }, []);

  function chooseFile(file) {
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
    previewUrl.current = file ? URL.createObjectURL(file) : "";
    setImagePreview(previewUrl.current);
    setOcrFile(file);
  }

  function handleModelAnswerFileSelect(event) {
    const file = event.target.files?.[0];
    if (!file) {
      setModelAnswerFileName("");
      return;
    }

    setModelAnswerFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      setModelAnswer((current) => (current && current.trim() ? `${current}\n\n${text}` : text).trim());
    };
    reader.onerror = () => {
      setError("Could not read the selected model-answer file.");
    };
    reader.readAsText(file);
  }

  async function handleModelAnswerImageSelect(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    setError("");
    setModelImageLoading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await apiFetch("/ocr?store_image=false", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) throw new Error(await readError(response, "Could not read the model-answer image."));
      const data = await response.json();
      if (!data.extracted_text?.trim()) {
        throw new Error("No text was detected in the selected model-answer image.");
      }
      setModelAnswer((current) => (
        current.trim() ? `${current}\n\n${data.extracted_text}` : data.extracted_text
      ).trim());
      setModelAnswerFileName(file.name);
    } catch (err) {
      setError(err.message);
    } finally {
      setModelImageLoading(false);
      event.target.value = "";
    }
  }

  function generateRubric() {
    setError("");
    if (!modelAnswer.trim()) {
      setError("Enter or load a model answer first.");
      return;
    }
    const requestedTotal = Number(totalMarks);
    if (!Number.isFinite(requestedTotal) || requestedTotal <= 0 || requestedTotal > 1000) {
      setError("Total marks must be greater than 0 and no more than 1000.");
      return;
    }
    if (rubricText.trim() && !window.confirm("Replace the current rubric with one generated from the model answer?")) {
      return;
    }
    const generated = generateRubricFromAnswer(modelAnswer, requestedTotal);
    if (!generated) {
      setError("No rubric points could be found in the model answer.");
      return;
    }
    setRubricText(generated);
  }

  async function extractText() {
    if (!ocrFile) {
      setError("Choose an answer-sheet image first.");
      return;
    }
    setOcrLoading(true);
    setError("");
    const formData = new FormData();
    formData.append("file", ocrFile);
    try {
      const response = await apiFetch("/ocr", { method: "POST", body: formData });
      if (!response.ok) throw new Error(await readError(response, "OCR could not extract text."));
      const data = await response.json();
      setStudentAnswer(data.extracted_text);
      setStoredImagePath(data.image_path);
      setSections(data.sections || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setOcrLoading(false);
    }
  }

  async function gradeAnswer(event) {
    event.preventDefault();
    setGrading(true);
    setError("");
    setSaved("");
    setResult(null);
    try {
      const rubric = parseRubric(rubricText);
      const response = await apiFetch("/grade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_answer: modelAnswer, student_answer: studentAnswer, rubric }),
      });
      if (!response.ok) throw new Error(await readError(response, "Unable to grade the answer."));
      const data = await response.json();
      setRubricItems(rubric);
      setResult(data);
      setFinalScore(data.score);
    } catch (err) {
      setError(err.message);
    } finally {
      setGrading(false);
    }
  }

  async function approveScore() {
    if (!result) return;
    setSaved("");
    setError("");
    const score = Number(finalScore);
    if (finalScore === "" || !Number.isFinite(score) || score < 0 || score > Number(result.max_marks)) {
      setError(`Final score must be between 0 and ${result.max_marks}.`);
      return;
    }
    try {
      const response = await apiFetch("/submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_name: studentName,
          question_title: questionTitle,
          model_answer: modelAnswer,
          student_answer: studentAnswer,
          rubric: rubricItems,
          image_path: storedImagePath || null,
          ai_score: Number(result.score),
          final_score: score,
          max_marks: Number(result.max_marks),
        }),
      });
      if (!response.ok) throw new Error(await readError(response, "Could not save the grade."));
      const data = await response.json();
      setSaved(`Saved successfully (submission #${data.submission_id}).`);
      onSaved();
    } catch (err) {
      setError(err.message);
    }
  }

  const percent = result && result.max_marks ? Math.round((result.score / result.max_marks) * 100) : 0;

  return (
    <div className="space-y-6">
      <Card title="Grade an answer" subtitle="Upload a typed answer sheet, check the extracted text, then grade it against your rubric.">
        <form onSubmit={gradeAnswer} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Student name">
              <Input value={studentName} onChange={(e) => setStudentName(e.target.value)}
                placeholder="Example: Adhi Kumar" required />
            </Field>
            <Field label="Question title">
              <Input value={questionTitle} onChange={(e) => setQuestionTitle(e.target.value)}
                placeholder="Example: Explain photosynthesis" required />
            </Field>
          </div>

          <div className="space-y-2">
            <Field label="Model answer">
              <Textarea value={modelAnswer} onChange={(e) => setModelAnswer(e.target.value)}
                placeholder="Teacher's reference answer" required />
            </Field>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <label className="inline-flex cursor-pointer items-center justify-center rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
                <span>Choose text file</span>
                <input type="file" accept=".txt,.md,.rtf,.csv,text/plain" className="hidden" onChange={handleModelAnswerFileSelect} />
              </label>
              <label className={`inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition ${modelImageLoading ? "cursor-wait opacity-60" : "cursor-pointer hover:bg-slate-50"}`}>
                <span>{modelImageLoading ? "Reading image…" : "Choose image"}</span>
                <input type="file" accept="image/png,image/jpeg" className="hidden"
                  disabled={modelImageLoading} onChange={handleModelAnswerImageSelect} />
              </label>
              <span className="text-sm text-slate-500">
                {modelAnswerFileName ? `Loaded: ${modelAnswerFileName}` : "Optional: load a text or image file for the model answer"}
              </span>
            </div>
          </div>

          <div className="rounded-lg border-2 border-dashed border-emerald-200 bg-emerald-50/50 p-4">
            <Field label="Answer sheet image" hint="PNG or JPEG, typed English text, up to 10 MB">
              <input type="file" accept="image/png,image/jpeg"
                onChange={(e) => chooseFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-100 file:px-3 file:py-2 file:text-sm file:font-medium file:text-emerald-900 hover:file:bg-emerald-200" />
            </Field>
            <Button className="mt-3" onClick={extractText} disabled={ocrLoading || !ocrFile}>
              {ocrLoading ? "Extracting text…" : "Extract text from image"}
            </Button>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <p className="mb-1.5 text-sm font-medium text-slate-700">Uploaded answer sheet</p>
              <div className="flex h-56 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-slate-50 p-2">
                {imagePreview ? (
                  <img src={imagePreview} alt="Uploaded answer sheet preview"
                    className="max-h-full max-w-full object-contain" />
                ) : (
                  <p className="text-sm text-slate-400">Select an image to see its preview</p>
                )}
              </div>
            </div>
            <Field label="Student answer (editable OCR text)">
              <Textarea value={studentAnswer} onChange={(e) => setStudentAnswer(e.target.value)}
                placeholder="OCR text will appear here after extraction" required className="h-56" />
            </Field>
          </div>

          {sections.length > 1 && (
            <Alert tone="info" title="Several answers detected on this sheet">
              <div className="mt-2">
                <Select defaultValue="" aria-label="Choose the answer to grade"
                  onChange={(e) => {
                    const picked = sections[Number(e.target.value)];
                    if (picked) setStudentAnswer(picked.text);
                  }}>
                  <option value="" disabled>Choose the answer to grade…</option>
                  {sections.map((s, i) => (
                    <option key={s.label + i} value={i}>{s.label}: {s.text.slice(0, 70)}</option>
                  ))}
                </Select>
              </div>
            </Alert>
          )}

          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-slate-700">Rubric (one point per line)</p>
              <div className="flex flex-wrap items-end gap-2">
                <label className="flex items-center gap-2 whitespace-nowrap text-sm font-medium text-slate-700">
                  <span>Marks for generated rubric</span>
                  <span className="w-24">
                    <Input type="number" min="0.5" max="1000" step="0.5" value={totalMarks}
                      onChange={(event) => setTotalMarks(event.target.value)} />
                  </span>
                </label>
                <Button type="button" size="sm" variant="secondary" onClick={generateRubric}>
                  Generate from model answer
                </Button>
              </div>
            </div>
            <p className="text-xs text-slate-500">Format: Rubric point | keywords | expected meaning | marks</p>
            <Textarea value={rubricText} onChange={(e) => setRubricText(e.target.value)}
              placeholder={RUBRIC_PLACEHOLDER} required className="min-h-36 font-mono text-xs leading-relaxed" />
          </div>

          {error && <Alert tone="error">{error}</Alert>}

          <Button type="submit" disabled={grading}>{grading ? "Grading…" : "Grade answer"}</Button>
        </form>
      </Card>

      {result && (
        <Card title="AI suggested result" subtitle="Review the breakdown, adjust the score if needed, then approve.">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <div className="flex h-28 w-28 shrink-0 flex-col items-center justify-center rounded-full bg-emerald-50 ring-8 ring-emerald-100">
              <span className="text-3xl font-bold text-emerald-800">{result.score}</span>
              <span className="text-xs text-emerald-700">out of {result.max_marks}</span>
            </div>
            <div className="flex-1">
              <div className="mb-1 flex justify-between text-sm text-slate-600">
                <span>Rubric coverage</span>
                <span className="font-medium">{result.confidence}%</span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                <div className={`h-full rounded-full ${percent >= 60 ? "bg-emerald-500" : "bg-amber-500"}`}
                  style={{ width: `${Math.min(100, result.confidence)}%` }} />
              </div>
            </div>
          </div>

          <div className="mt-5 space-y-3">
            {result.needs_review && (
              <Alert tone="warning" title="Teacher review required">{result.review_reason}</Alert>
            )}
            {result.semantic_available === false && (
              <Alert tone="info">
                Semantic matching is unavailable on the server, so this score uses keyword matching only.
              </Alert>
            )}
          </div>

          <ul className="mt-5 divide-y divide-slate-100 rounded-lg border border-slate-200">
            {result.rubric_breakdown.map((item, index) => (
              <li key={`${item.point}-${index}`} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-900">{item.point}</p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {item.semantic_similarity !== null && item.semantic_similarity !== undefined
                      ? `Semantic similarity ${item.semantic_similarity}%`
                      : "Semantic similarity not available"}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <Badge tone={item.matched ? "green" : "slate"}>{item.match_method}</Badge>
                  <span className="w-12 text-right text-sm font-semibold text-slate-900">
                    {item.awarded_marks} / {item.marks}
                  </span>
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-6 rounded-lg border border-[var(--line)] bg-emerald-50/40 p-4">
            <h3 className="text-sm font-semibold text-slate-900">Teacher review</h3>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <div className="w-36">
                <Field label="Final score">
                  <Input type="number" min="0" max={result.max_marks} step="0.1" value={finalScore}
                    onChange={(e) => { setFinalScore(e.target.value); setSaved(""); }} />
                </Field>
              </div>
              <Button onClick={approveScore}>Approve and save final score</Button>
            </div>
            {saved && <div className="mt-3"><Alert tone="success">{saved}</Alert></div>}
          </div>
        </Card>
      )}
    </div>
  );
}
