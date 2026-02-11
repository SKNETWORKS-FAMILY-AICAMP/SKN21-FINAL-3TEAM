import { Link } from 'react-router-dom';
import useAuthStore from '../../store/authStore';

export default function Header() {
  const _user = useAuthStore((s) => s.user);

  return (
    <header className="flex justify-between items-center py-6 sticky top-0 bg-surface-main z-10">
      <div>
        <h1 className="text-2xl font-bold text-neutral-main" id="page-title"></h1>
        <p className="text-sm text-neutral-sub mt-1" id="page-subtitle"></p>
      </div>
      <div className="flex items-center gap-3">
        <Link to="/documents" className="flex items-center gap-2 bg-surface-card border border-neutral-border rounded-md px-4 py-2 min-w-[280px] transition hover:border-primary-300 focus-within:border-primary-300 focus-within:shadow-[0_0_0_3px_rgba(110,135,160,0.1)]">
          <span>🔍</span>
          <input type="text" placeholder="규정 검색 (정보보안, 인사, 개발)" className="border-none bg-transparent text-[0.8125rem] text-neutral-main w-full outline-none placeholder:text-neutral-muted" />
        </Link>
        <button className="w-10 h-10 rounded-sm border border-neutral-border bg-surface-card flex items-center justify-center text-base relative transition hover:border-primary-300">
          <span>🔔</span>
          <span className="absolute top-2 right-2 w-2 h-2 bg-error rounded-full border-2 border-surface-card" />
        </button>
      </div>
    </header>
  );
}
