/* ═══════════════════════════════════════════════════════════════════════
   Loading Spinner with progress bar.
   ═══════════════════════════════════════════════════════════════════════ */

interface LoadingSpinnerProps {
  progress?: number;
  message?: string;
}

export default function LoadingSpinner({ progress = 0, message = 'Loading...' }: LoadingSpinnerProps) {
  return (
    <div className="loading-container" id="loading-spinner">
      <div className="loading-spinner" />
      {progress > 0 && (
        <div className="progress-bar">
          <div
            className="progress-bar__fill"
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
      )}
      <div className="loading-text">{message}</div>
      {progress > 0 && (
        <div className="loading-text" style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)' }}>
          {progress}%
        </div>
      )}
    </div>
  );
}
