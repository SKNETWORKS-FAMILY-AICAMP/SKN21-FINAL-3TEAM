import { useState, useEffect } from 'react';

const MIN = 14;
const MAX = 22;
const STEP = 2;
const DEFAULT = 16;
const STORAGE_KEY = 'app-font-size';

export default function FontSizeControl() {
  const [size, setSize] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? Number(saved) : DEFAULT;
  });

  useEffect(() => {
    document.documentElement.style.fontSize = size + 'px';
    localStorage.setItem(STORAGE_KEY, size);
  }, [size]);

  const decrease = () => setSize((s) => Math.max(MIN, s - STEP));
  const increase = () => setSize((s) => Math.min(MAX, s + STEP));

  return (
    <div className="fixed bottom-5 right-5 flex items-center gap-1 bg-surface-card border border-neutral-border rounded-lg shadow-lg px-1.5 py-1.5 z-50">
      <button
        onClick={decrease}
        disabled={size <= MIN}
        className="w-9 h-9 rounded-md text-sm font-bold text-neutral-main hover:bg-surface-hover transition disabled:opacity-30 disabled:cursor-not-allowed"
      >
        가-
      </button>
      <div className="w-px h-5 bg-neutral-divider" />
      <button
        onClick={increase}
        disabled={size >= MAX}
        className="w-9 h-9 rounded-md text-sm font-bold text-neutral-main hover:bg-surface-hover transition disabled:opacity-30 disabled:cursor-not-allowed"
      >
        가+
      </button>
    </div>
  );
}
