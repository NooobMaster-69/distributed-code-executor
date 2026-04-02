export default function OutputPanel({ status, result, error, running }) {
  if (error) {
    return (
      <div className="output-wrapper">
        <div className="output-block output-error">
          <span className="output-label">Error</span>
          <pre>{error}</pre>
        </div>
      </div>
    );
  }

  if (!status && !result) {
    return (
      <div className="output-wrapper">
        <div className="output-empty">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" opacity="0.3">
            <rect x="6" y="6" width="36" height="36" rx="8" stroke="currentColor" strokeWidth="2" />
            <path d="M16 18l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <line x1="26" y1="30" x2="34" y2="30" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <p>Run your code to see output here</p>
        </div>
      </div>
    );
  }

  if (running && !result) {
    return (
      <div className="output-wrapper">
        <div className="output-loading">
          <div className="loader" />
          <p>
            {status === 'SUBMITTING' && 'Submitting job...'}
            {status === 'QUEUED' && 'Waiting in queue...'}
            {status === 'RUNNING' && 'Executing code...'}
            {!['SUBMITTING', 'QUEUED', 'RUNNING'].includes(status) && 'Processing...'}
          </p>
        </div>
      </div>
    );
  }

  if (!result) return null;

  return (
    <div className="output-wrapper">
      {result.stdout && (
        <div className="output-block output-stdout">
          <span className="output-label">stdout</span>
          <pre>{result.stdout}</pre>
        </div>
      )}

      {result.stderr && (
        <div className="output-block output-stderr">
          <span className="output-label">stderr</span>
          <pre>{result.stderr}</pre>
        </div>
      )}

      {result.error && (
        <div className="output-block output-error">
          <span className="output-label">error</span>
          <pre>{result.error}</pre>
        </div>
      )}

      {!result.stdout && !result.stderr && !result.error && (
        <div className="output-block output-stdout">
          <span className="output-label">output</span>
          <pre className="output-muted">(no output)</pre>
        </div>
      )}

      <div className="output-meta">
        <div className="meta-item">
          <span className="meta-key">Status</span>
          <span className={`meta-value status-color-${result.status?.toLowerCase()}`}>
            {result.status}
          </span>
        </div>
        <div className="meta-item">
          <span className="meta-key">Exit Code</span>
          <span className={`meta-value ${result.exit_code === 0 ? 'exit-ok' : 'exit-err'}`}>
            {result.exit_code}
          </span>
        </div>
        <div className="meta-item">
          <span className="meta-key">Time</span>
          <span className="meta-value">{result.execution_time_ms?.toFixed(1)} ms</span>
        </div>
        <div className="meta-item">
          <span className="meta-key">Language</span>
          <span className="meta-value">{result.language}</span>
        </div>
        {result.timed_out && (
          <div className="meta-item">
            <span className="meta-key">Timed Out</span>
            <span className="meta-value exit-err">Yes</span>
          </div>
        )}
      </div>
    </div>
  );
}
