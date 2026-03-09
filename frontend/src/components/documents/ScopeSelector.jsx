import { useState } from 'react';
import useAuthStore from '../../store/authStore';

export default function ScopeSelector({ value, onChange }) {
  const [selected, setSelected] = useState(value || 'company');
  const user = useAuthStore((s) => s.user);
  const hasTeam = !!user?.team;

  const handleClick = (v) => { setSelected(v); onChange?.(v); };

  const scopes = [
    { v: 'company', l: '회사 문서', desc: '전체 사용자가 열람 가능' },
    { v: 'team', l: '팀 문서', desc: hasTeam ? `${user.team} 팀원만 열람 가능` : '소속 팀이 없습니다' },
  ];

  return (
    <div className="flex flex-col items-center gap-1 mt-3">
      <div className="flex gap-2">
        {scopes.map(({ v, l }) => {
          const disabled = v === 'team' && !hasTeam;
          return (
            <button
              key={v}
              onClick={() => !disabled && handleClick(v)}
              disabled={disabled}
              title={disabled ? '소속 팀이 없어 팀 문서를 사용할 수 없습니다' : ''}
              className={`px-4 py-1.5 rounded-full border text-xs font-medium transition ${
                disabled
                  ? 'bg-surface-hover text-neutral-muted border-neutral-border cursor-not-allowed opacity-50'
                  : selected === v
                    ? 'bg-primary-700 text-white border-primary-700'
                    : 'bg-surface-card text-neutral-sub border-neutral-border'
              }`}
            >
              {l}
            </button>
          );
        })}
      </div>
      <span className="text-[11px] text-neutral-muted">
        {scopes.find((s) => s.v === selected)?.desc}
      </span>
    </div>
  );
}
