const inputBase =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 " +
  "placeholder:text-slate-400 shadow-sm focus:border-emerald-700 focus:outline-none " +
  "focus:ring-2 focus:ring-emerald-100 disabled:bg-slate-100";

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export function Input(props) {
  return <input {...props} className={`${inputBase} ${props.className || ""}`} />;
}

export function Textarea(props) {
  return (
    <textarea
      {...props}
      className={`${inputBase} min-h-28 resize-y ${props.className || ""}`}
    />
  );
}

export function Select(props) {
  return <select {...props} className={`${inputBase} ${props.className || ""}`} />;
}

const variants = {
  primary: "bg-emerald-800 text-white hover:bg-emerald-900 focus-visible:ring-emerald-300",
  secondary:
    "bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-emerald-50 focus-visible:ring-emerald-200",
  danger: "bg-rose-600 text-white hover:bg-rose-700 focus-visible:ring-rose-300",
  ghost: "text-slate-600 hover:bg-slate-100 focus-visible:ring-slate-300",
};

export function Button({ variant = "primary", size = "md", className = "", ...props }) {
  const sizes = size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-4 py-2 text-sm";
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium shadow-sm transition
        focus:outline-none focus-visible:ring-4 disabled:cursor-not-allowed disabled:opacity-60
        ${sizes} ${variants[variant]} ${className}`}
    />
  );
}

export function Card({ title, subtitle, action, children, className = "" }) {
  return (
    <section
      className={`rounded-lg border border-[var(--line)] bg-[var(--paper)] p-5 shadow-[0_12px_32px_rgba(26,56,43,0.06)] sm:p-6 ${className}`}
    >
      {(title || action) && (
        <header className="mb-5 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">{title}</h2>
            {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

const tones = {
  error: "border-rose-200 bg-rose-50 text-rose-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  info: "border-sky-200 bg-sky-50 text-sky-800",
};

export function Alert({ tone = "info", title, children }) {
  return (
    <div role={tone === "error" ? "alert" : "status"}
      className={`rounded-lg border px-4 py-3 text-sm ${tones[tone]}`}>
      {title && <p className="font-semibold">{title}</p>}
      {children && <div className={title ? "mt-0.5" : ""}>{children}</div>}
    </div>
  );
}

const badgeTones = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  slate: "bg-slate-100 text-slate-600 ring-slate-500/20",
  indigo: "bg-emerald-50 text-emerald-800 ring-emerald-700/20",
};

export function Badge({ tone = "slate", children }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${badgeTones[tone]}`}>
      {children}
    </span>
  );
}
