const LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'node', label: 'Node.js' },
  { value: 'bash', label: 'Bash' },
  { value: 'powershell', label: 'PowerShell' },
];

export default function Controls({
  language,
  timeout,
  running,
  onLanguageChange,
  onTimeoutChange,
  onRun,
}) {
  return (
    <div className="controls">
      <select
        id="language-select"
        className="select"
        value={language}
        onChange={(e) => onLanguageChange(e.target.value)}
        disabled={running}
      >
        {LANGUAGES.map((l) => (
          <option key={l.value} value={l.value}>
            {l.label}
          </option>
        ))}
      </select>

      <div className="timeout-group">
        <label htmlFor="timeout-input" className="timeout-label">
          Timeout
        </label>
        <input
          id="timeout-input"
          type="number"
          className="timeout-input"
          value={timeout}
          min={1}
          max={30}
          onChange={(e) => onTimeoutChange(Number(e.target.value))}
          disabled={running}
        />
        <span className="timeout-unit">s</span>
      </div>

      <button
        id="run-button"
        className="run-btn"
        onClick={onRun}
        disabled={running}
      >
        {running ? (
          <>
            <span className="spinner" />
            Running
          </>
        ) : (
          <>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
              <path d="M3 1.5v11l9-5.5L3 1.5z" />
            </svg>
            Run
          </>
        )}
      </button>
    </div>
  );
}
