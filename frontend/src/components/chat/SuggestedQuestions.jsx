import { SUGGESTED_QUESTIONS } from '../../utils/constants';

export default function SuggestedQuestions({ questions = SUGGESTED_QUESTIONS, onSelect }) {
  return (
    <div className="flex flex-col items-center gap-6 py-20">
      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center text-white text-xl font-bold">
        AI
      </div>
      <div>
        <p className="text-neutral-sub text-sm text-center mb-1">무엇을 도와드릴까요?</p>
        <p className="text-neutral-muted text-xs text-center">아래 질문을 클릭하거나, 직접 입력해보세요</p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center max-w-md">
        {questions.map((q, i) => (
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
