import { useState } from 'react';
import { SUGGESTED_QUESTIONS, SUGGESTED_QUESTION_CATEGORIES } from '../../utils/constants';

export default function SuggestedQuestions({ questions = SUGGESTED_QUESTIONS, onSelect }) {
  const [activeCategory, setActiveCategory] = useState('all');

  const filtered = activeCategory === 'all'
    ? questions
    : questions.filter((q) => q.category === activeCategory);

  return (
    <div className="flex flex-col items-center gap-6 py-20">
      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-white text-xl font-bold">
        AI
      </div>
      <div>
        <p className="text-neutral-sub text-sm text-center mb-1">무엇을 도와드릴까요?</p>
        <p className="text-neutral-muted text-xs text-center">카테고리를 선택하거나, 직접 입력해보세요</p>
      </div>

      {/* 카테고리 탭 */}
      <div className="flex gap-2 flex-wrap justify-center">
        {SUGGESTED_QUESTION_CATEGORIES.map((cat) => (
          <button
            key={cat.key}
            onClick={() => setActiveCategory(cat.key)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
              activeCategory === cat.key
                ? 'bg-primary-700 text-white'
                : 'bg-surface-card border border-neutral-border text-neutral-sub hover:bg-primary-50 hover:border-primary-300'
            }`}
          >
            {cat.icon} {cat.label}
          </button>
        ))}
      </div>

      {/* 추천 질문 목록 */}
      <div className="flex flex-wrap gap-2 justify-center max-w-lg">
        {filtered.map((q, i) => (
          <button
            key={i}
            onClick={() => onSelect?.(q.text)}
            className="px-3.5 py-2 rounded-full border border-neutral-border text-sm text-neutral-main hover:bg-primary-50 hover:border-primary-300 transition"
          >
            {q.text}
          </button>
        ))}
      </div>
    </div>
  );
}
