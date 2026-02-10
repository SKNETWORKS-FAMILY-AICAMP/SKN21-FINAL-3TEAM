import { Link } from 'react-router-dom';

export default function RiskAlert({ title, description, to = '/documents' }) {
  return (
    <div className="flex items-center gap-3.5 bg-error-bg border border-error/20 rounded-md px-5 py-3.5 mb-6">
      <span className="text-xl">🚨</span>
      <div className="flex-1">
        <div className="text-sm font-bold text-error">{title}</div>
        <div className="text-xs text-neutral-sub mt-0.5">{description}</div>
      </div>
      <Link to={to} className="btn-primary">자세히 보기</Link>
    </div>
  );
}
