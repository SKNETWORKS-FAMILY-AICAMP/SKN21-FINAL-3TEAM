import { Link } from 'react-router-dom';

const iconBg = { blue: 'bg-primary-50', purple: 'bg-accent-50', green: 'bg-success-bg', red: 'bg-error-bg' };

export default function StatCard({ icon, iconColor = 'blue', value, label, trend, to }) {
  const Wrapper = to ? Link : 'div';
  return (
    <Wrapper to={to} className="card p-5 transition hover:shadow-md hover:-translate-y-px hover:border-primary-300 block">
      <div className="flex justify-between items-center mb-3">
        <div className={`w-10 h-10 rounded-sm flex items-center justify-center text-lg ${iconBg[iconColor]}`}>{icon}</div>
        {trend && <span className="text-xs font-semibold px-2 py-0.5 rounded-full text-success bg-success-bg">{trend}</span>}
      </div>
      <div className="font-display text-[2rem] font-bold text-primary-700 leading-none">{value}</div>
      <div className="text-[0.8125rem] text-neutral-sub mt-1">{label}</div>
    </Wrapper>
  );
}
