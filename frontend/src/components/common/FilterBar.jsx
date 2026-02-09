export default function FilterBar({ tabs, activeTab, onTabChange, filters, actions }) {
  return (
    <div className="flex gap-3 mb-5 items-center flex-wrap">
      {tabs && (
        <div className="flex gap-2">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => onTabChange?.(tab)}
              className={`px-4 py-1.5 rounded-full border text-[13px] font-medium transition ${
                activeTab === tab
                  ? 'bg-primary-700 text-white border-primary-700'
                  : 'bg-surface-card text-neutral-sub border-neutral-border hover:border-primary-300 hover:text-primary-700'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      )}
      {filters}
      {actions && <div className="ml-auto">{actions}</div>}
    </div>
  );
}
