import { Link } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';

export default function RiskAlert({ title, description, to = '/documents' }) {
  return (
    <div className="flex items-center gap-3.5 bg-error-bg border border-neutral-border rounded-md px-5 py-3.5 mb-6">
      <ShieldAlert size={22} className="text-error flex-shrink-0" />
      <div className="flex-1">
        <div className="text-sm font-bold text-error">{title}</div>
        <div className="text-xs text-neutral-sub mt-0.5">{description}</div>
      </div>
      <Link to={to} className="btn-primary">자세히 보기</Link>
    </div>
  );
}
