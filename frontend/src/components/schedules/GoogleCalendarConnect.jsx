export default function GoogleCalendarConnect({ connected = false, email }) {
  return (
    <div className="flex items-center gap-3 px-5 py-3.5 bg-surface-card border border-neutral-border rounded-md mb-5">
      <div className={`flex items-center gap-1.5 text-[13px] font-medium ${connected ? 'text-success' : 'text-neutral-muted'}`}>
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-success' : 'bg-neutral-muted'}`} />
        {connected ? 'Google Calendar 연결됨' : 'Google Calendar 미연결'}
      </div>
      {email && <span className="text-xs text-neutral-muted ml-2">{email}</span>}
      <button className="btn-outline ml-auto text-xs">{connected ? '연결 해제' : '연결하기'}</button>
    </div>
  );
}
