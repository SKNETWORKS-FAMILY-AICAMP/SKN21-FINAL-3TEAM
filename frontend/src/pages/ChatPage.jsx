import { useState, useEffect, useMemo, useRef } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { MessageSquarePlus, Menu, CheckCircle, XCircle, AlertTriangle, HelpCircle, ShieldCheck, FileText, Search, MessageCircle, Copy, Star, CalendarPlus } from 'lucide-react';
import ChatWindow from '../components/chat/ChatWindow';
import MessageBubble from '../components/chat/MessageBubble';
import StreamingMessage from '../components/chat/StreamingMessage';

import ErrorMessage from '../components/chat/ErrorMessage';
import SuggestedQuestions from '../components/chat/SuggestedQuestions';
import RegulationPanel from '../components/chat/RegulationPanel';
import DocumentViewPanel from '../components/chat/DocumentViewPanel';
import ChatSessionSidebar from '../components/chat/ChatSessionSidebar';
import JudgmentCard from '../components/chat/JudgmentCard';
import ScheduleCard from '../components/chat/ScheduleCard';
import ScheduleConfirmCard from '../components/chat/ScheduleConfirmCard';
import GenerateCard, { ScheduleSuggestSection } from '../components/chat/GenerateCard';
import MarkdownText from '../components/chat/MarkdownText';
import SourceItem from '../components/chat/SourceItem';
import SourceList from '../components/chat/SourceList';
import CompoundCard from '../components/chat/CompoundCard';
import useChat from '../hooks/useChat';
import useChatStore from '../store/chatStore';
import { listRegulations } from '../api/regulations';
import { listDocuments, downloadDocument, uploadDocument } from '../api/documents';
import { toast } from '../store/toastStore';

function exportChat(messages) {
  if (messages.length === 0) return;

  const now = new Date();
  const dateStr = now.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\. /g, '-').replace('.', '');
  const timeStr = now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });

  const lines = [`AI 챗봇 대화 기록`, `내보낸 시각: ${dateStr} ${timeStr}`, `총 ${messages.length}개 메시지`, '─'.repeat(40), ''];

  messages.forEach((msg) => {
    const role = msg.role === 'user' ? '[나]' : '[AI]';
    lines.push(`${role}:`);
    lines.push(msg.content);
    lines.push('');
  });

  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `chat-export-${dateStr}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

const USAGE_GUIDE_TEXT = `1. 질문 입력: 업무와 관련된 궁금한 점이나 요청사항을 질문창에 입력하세요.
2. 즉시 답변: 듀드가 최대한 빠르게 정확한 답변을 제공합니다.
3. 다양한 업무: 문서 작성, 일정 관리, 규정 판단 등 다양한 업무에 활용할 수 있습니다.
4. 예시:
   - 규정 판단: "출장비 사용 가능한가요?"
   - 문서: "계약서 검색해줘", "회의록 요약해줘", "보고서 작성해줘"
   - 일정: "내일 오후 2시 회의 등록해줘", "이번주 일정 보여줘"`;

const RESULT_MAP = { yes: '가능', no: '불가', conditional: '조건부 가능', no_regulation: '규정 없음' };

// LLM 응답 텍스트에서 raw enum 값을 한국어로 치환
function cleanResultText(text) {
  if (!text) return text;
  return text
    .replace(/[""\u201C\u201D]no_regulation[""\u201C\u201D]/g, '"규정 없음"')
    .replace(/\bno_regulation\b/g, '규정 없음');
}

const RESULT_BADGE = {
  yes: { icon: CheckCircle, bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-700', iconColor: 'text-green-500' },
  no: { icon: XCircle, bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', iconColor: 'text-red-500' },
  conditional: { icon: AlertTriangle, bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', iconColor: 'text-amber-500' },
  no_regulation: { icon: HelpCircle, bg: 'bg-surface-sub', border: 'border-neutral-border', text: 'text-neutral-sub', iconColor: 'text-neutral-muted' },
};

function renderCardMessage(msg, onSelectClarify, onSelectDoc, messages = [], index = -1, isLastAndStreaming = false) {
  const { resultIntent, agentResponse, content } = msg;
  const data = agentResponse || {};

  switch (resultIntent) {
    case 'judgment': {
      // 사용자의 질문 내용 확인 (이전 메시지)
      const userMsg = index > 0 ? messages[index - 1]?.content || '' : '';
      // '규정', '알려줘', '설명'만 있는 경우는 정보 조회로 간주 (의문형/판단형 키워드가 없을 때)
      const isJudgmentRequest = /가능|요건|조건|되나요|있나요|수 있|있습니|허용|금지|위반|처벌|준수/.test(userMsg);

      // 'none'이나 판단 결과가 명확하지 않거나, 단순 정보 조회인 경우 배지 숨김
      const isInformational = !data.result || data.result === 'none' || data.result === 'info' || (data.result === 'yes' && !isJudgmentRequest);

      const resultLabel = isInformational ? null : (RESULT_MAP[data.result] || data.result || '판단 완료');
      const badge = isInformational ? null : (RESULT_BADGE[data.result] || null);

      const regType = data.result === 'no' ? 'deny' : data.result === 'conditional' ? 'conditional' : 'ref';
      const regulations = (data.regulations || []).map((r) => ({
        name: `${r.name || ''} ${r.article || ''}`.trim(),
        type: regType,
        verdict: r.content || '',
      }));
      return (
        <>
          {/* 판단 배지 (불가/가능 등) — 맨 위 */}
          {resultLabel && badge && (() => {
            const Icon = badge.icon;
            return (
              <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-semibold mb-2 ${badge.bg} ${badge.border} ${badge.text}`}>
                <Icon size={16} className={badge.iconColor} />
                {resultLabel}
              </div>
            );
          })()}
          {/* 줄글 (스트리밍 텍스트) */}
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed shadow-sm">
            <MarkdownText>{cleanResultText(content || data.reasoning)}</MarkdownText>
          </div>
          {/* 규정 + 신뢰도 카드 */}
          <JudgmentCard summary={null} regulations={regulations} confidenceBreakdown={data.confidence_breakdown} warnings={data.warnings} confidence={data.confidence} />
        </>
      );
    }

    case 'doc_retrieve':
    case 'doc_search': {
      const subType = data.sub_type || '';
      const sources = data.sources || data.references || [];
      const tags = data.tags || [];
      const summaryText = data.summary || content || data.answer || data.message;
      const citations = data.citations || [];
      const qaConfidence = typeof data.confidence === 'number' ? data.confidence : null;
      const ragStatus = data.rag_status;

      // 카드 복사 헬퍼
      const copyCardText = (text) => {
        navigator.clipboard.writeText(text).catch(() => {});
      };

      // sub_type=summary → 요약 카드
      if (subType === 'summary' || tags.length > 0) {
        const topicHint = tags[0] || '';
        return (
          <div className="bg-surface-card rounded-lg border border-neutral-border overflow-hidden">
            <div className="px-4 py-3 border-b border-neutral-divider flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold text-sm text-primary-700">
                <FileText size={16} />
                문서 요약
              </div>
              <button onClick={() => copyCardText(summaryText)} className="text-neutral-muted hover:text-neutral-main transition" title="복사">
                <Copy size={14} />
              </button>
            </div>
            <div className="p-4 space-y-2">
              {tags.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[0.75rem] text-neutral-muted">태그:</span>
                  {tags.map((tag, i) => (
                    <span key={i} className="inline-block px-2 py-0.5 text-[0.75rem] rounded-full bg-primary-50 text-primary-700">
                      #{tag}
                    </span>
                  ))}
                </div>
              )}
              {summaryText && (
                <div>
                  <span className="text-[0.75rem] text-neutral-muted">요약:</span>
                  <p className="text-[0.8125rem] text-neutral-main leading-[1.7] mt-1">{summaryText}</p>
                </div>
              )}
              {/* 출처 문서 표시 */}
              {data.document_id && (
                <div className="text-[0.6875rem] text-neutral-muted mt-2">
                  출처: 문서 #{data.document_id}
                </div>
              )}
              {/* 규정 경고 */}
              {data.regulation_check?.notes?.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  {data.regulation_check.notes.map((n, i) => (
                    <div key={i} className={`flex items-start gap-1.5 p-2.5 rounded-lg border text-xs ${
                      n.result === 'no' ? 'bg-red-50 border-red-200 text-red-700' :
                      n.result === 'conditional' ? 'bg-yellow-50 border-yellow-200 text-yellow-700' :
                      'bg-green-50 border-green-200 text-green-700'
                    }`}>
                      <AlertTriangle size={13} className="shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold">{n.result === 'no' ? '[위반]' : n.result === 'conditional' ? '[조건부]' : '[부합]'} {n.topic}</span>
                        <p className="text-[0.6875rem] mt-0.5">{n.reason}</p>
                        {n.regulation && <p className="text-[0.625rem] mt-0.5 italic opacity-75">근거: {n.regulation}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {Array.isArray(data.warnings) && data.warnings.length > 0 && !data.regulation_check?.notes?.length && (
                <div className="mt-3 space-y-1">
                  {data.warnings.map((w, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2">
                      <AlertTriangle size={13} className="text-yellow-500 mt-0.5 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      }

      // sub_type=qa → QA 카드
      if (subType === 'qa' || qaConfidence !== null) {
        const topScore = sources[0]?.score ?? qaConfidence ?? 0;
        const hintInfo = topScore >= 0.7 ? { text: 'text-green-600', hint: '관련도가 높은 문서를 기반으로 답변했습니다' } : topScore >= 0.4 ? { text: 'text-yellow-600', hint: '관련 문서를 참고했지만 정확하지 않을 수 있습니다' } : { text: 'text-red-600', hint: '관련도가 낮은 문서를 참고했습니다. 다시 질문해보세요' };
        return (
          <div className="bg-surface-card rounded-lg border border-neutral-border overflow-hidden">
            <div className="px-4 py-3 border-b border-neutral-divider flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold text-sm text-primary-700">
                <MessageCircle size={16} />
                문서 Q&A
              </div>
              <button onClick={() => copyCardText(content || data.answer || '')} className="text-neutral-muted hover:text-neutral-main transition" title="복사">
                <Copy size={14} />
              </button>
            </div>
            <div className="p-4">
              {(content || data.answer) && <div className="text-[0.8125rem] text-neutral-main leading-[1.7] mb-3.5"><MarkdownText>{content || data.answer}</MarkdownText></div>}
              {sources.length > 0 && (
                <div className="mb-3">
                  <div className="text-xs font-semibold text-neutral-sub mb-2">📎 참고 문서 ({sources.length}건)</div>
                  {sources.map((s, idx) => (
                    <SourceItem key={idx} source={s} index={idx} onSelect={onSelectDoc} />
                  ))}
                </div>
              )}
              {/* 규정 경고 (QA) */}
              {data.regulation_check?.notes?.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  {data.regulation_check.notes.map((n, i) => (
                    <div key={i} className={`flex items-start gap-1.5 p-2.5 rounded-lg border text-xs ${
                      n.result === 'no' ? 'bg-red-50 border-red-200 text-red-700' :
                      n.result === 'conditional' ? 'bg-yellow-50 border-yellow-200 text-yellow-700' :
                      'bg-green-50 border-green-200 text-green-700'
                    }`}>
                      <AlertTriangle size={13} className="shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold">{n.result === 'no' ? '[위반]' : n.result === 'conditional' ? '[조건부]' : '[부합]'} {n.topic}</span>
                        <p className="text-[0.6875rem] mt-0.5">{n.reason}</p>
                        {n.regulation && <p className="text-[0.625rem] mt-0.5 italic opacity-75">근거: {n.regulation}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <p className={`text-[0.6875rem] ${hintInfo.text}`}>{hintInfo.hint}</p>
            </div>
          </div>
        );
      }

      // 기본: 검색 카드
      {
        const firstSourceTitle = sources[0]?.title || '';
        return (
          <div className="bg-surface-card rounded-lg border border-neutral-border overflow-hidden">
            <div className="px-4 py-3 border-b border-neutral-divider flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold text-sm text-primary-700">
                <Search size={16} />
                문서 검색 결과{data.total_found ? ` (${data.total_found}건)` : ''}
              </div>
              {ragStatus === 'timeout' && (
                <span className="text-[0.625rem] text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">시간 초과</span>
              )}
            </div>
            <div className="p-4">
              {(content || data.answer || data.message) && <div className="text-[0.8125rem] text-neutral-main leading-[1.7] mb-3"><MarkdownText>{content || data.answer || data.message}</MarkdownText></div>}
              {sources.length > 0 && (
                <SourceList sources={sources} onSelect={onSelectDoc} />
              )}
            </div>
          </div>
        );
      }
    }

    case 'doc_generate': {
      const docData = data.data || {};
      const TEMPLATE_NAMES = { meeting_minutes: '회의록', report: '업무보고서', proposal: '제안서' };
      const templateName = data.template_name || TEMPLATE_NAMES[data.template_type] || '문서';

      const handleDocDownload = async () => {
        if (!data.document_id) { toast.warning('문서 ID가 없습니다.'); return; }
        try {
          const resp = await downloadDocument(data.document_id, 'docx');
          const url = URL.createObjectURL(resp.data);
          const a = document.createElement('a');
          a.href = url;
          a.download = `${templateName}.docx`;
          a.click();
          URL.revokeObjectURL(url);
        } catch (err) {
          toast.error('다운로드 실패: ' + (err.response?.data?.detail || err.message));
        }
      };

      // 회의록: action_items, 보고서: tasks → 통일된 형태로 전달
      let actionItems = [];
      let actionLabel = 'Action Items';
      if (data.template_type === 'meeting_minutes') {
        actionItems = data.action_items || docData.action_items || [];
      } else if (data.template_type === 'report') {
        actionLabel = '주요 업무';
        const tasks = docData.tasks || [];
        actionItems = tasks.map((t) => typeof t === 'string'
          ? { task: t, assignee: '', due_date: '' }
          : { task: t.item || t.task || t.content || '', assignee: t.assignee || '', due_date: t.end_date || t.due_date || '' }
        ).filter((t) => t.task);
      }

      const schedules = data.suggested_schedules || [];

      return (
        <div className="space-y-3">
          <GenerateCard
            title={String(docData.title || templateName)}
            templateType={data.template_type}
            fields={[]}
            actionItems={actionItems}
            actionLabel={actionLabel}
            onDownload={handleDocDownload}
            modelName={data.model_name || ''}
            regulationCheck={data.regulation_check}
            warnings={data.warnings}
            suggestedSchedules={[]}
          />
          {schedules.length > 0 && (
            <div className="bg-surface-card rounded-xl border border-neutral-border overflow-hidden shadow-sm">
              <div className="px-4 py-2.5 border-b border-neutral-divider flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[0.6875rem] font-semibold bg-success-bg text-success">
                  <CalendarPlus size={12} />
                  일정 Agent
                </span>
                <span className="text-xs text-neutral-muted">Action Items에서 {schedules.length}건의 일정을 감지했습니다</span>
              </div>
              <div className="p-4">
                <ScheduleSuggestSection items={schedules} />
              </div>
            </div>
          )}
        </div>
      );
    }

    case 'schedule_confirm':
    case 'schedule_clarify': {
      const sched = data.schedule || {};
      return (
        <ScheduleConfirmCard
          initialData={sched}
          onConfirmed={(apiResult) => {
            // 등록 완료 시 메시지의 intent/response를 schedule_add로 교체 → 자동 re-render
            msg.resultIntent = 'schedule_add';
            msg.agentResponse = {
              ...data,
              type: 'schedule_add',
              schedule: apiResult.schedule || sched,
              google_services: apiResult.google_services || {},
            };
          }}
        />
      );
    }

    case 'schedule_add': {
      const gs = data.google_services || {};
      const sched = data.schedule || {};
      return (
        <div>
          <ScheduleCard
            title={sched.title || data.title || data.summary || '일정 등록'}
            date={sched.start_time?.split('T')[0] || data.date || ''}
            time={sched.start_time?.split('T')[1]?.slice(0, 5) || data.time || ''}
            synced={gs.calendar_synced || data.synced || data.google_synced || false}
            meetLink={gs.meet_link || null}
            emailSent={gs.email_sent || false}
            emailCount={gs.email_count || 0}
            warnings={data.warnings}
            regulationCheck={data.regulation_check}
          />
          {content && (
            <div className="mt-2 bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
              {content}
            </div>
          )}
        </div>
      );
    }

    case 'doc_qa':       // 레거시 호환 — doc_retrieve로 통합됨
    case 'doc_search_qa': // 레거시 호환
    case 'doc_summary': { // 레거시 호환 — doc_retrieve sub_type=summary로 통합됨
      // doc_retrieve 케이스로 위임 (동일 렌더링 로직 재사용)
      return renderCardMessage({ ...msg, resultIntent: 'doc_retrieve' }, onSelectClarify, onSelectDoc, messages, index);
    }

    case 'template_pick': {
      const templates = data.templates || [];
      const originalQuery = index > 0 ? (messages[index - 1]?.content || '') : '';
      return (
        <div>
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
            {data.message || '사용할 양식을 선택해주세요:'}
          </div>
          {templates.length > 0 && (
            <div className="mt-2 flex flex-col gap-2 max-h-64 overflow-y-auto pr-1">
              {templates.map((tpl, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    useChatStore.getState().setSelectedTemplate(tpl.template_id, tpl.name, data.template_type);
                    onSelectClarify?.(originalQuery, { silent: true, forceIntent: 'doc_generate' });
                  }}
                  className={`p-3 border rounded-xl transition text-left hover:shadow-md hover:border-primary-300 ${tpl.recommended ? 'bg-primary-50/50 border-primary-300' : 'bg-surface-card border-neutral-border hover:bg-primary-50'}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    {tpl.is_system ? (
                      <Star size={14} className="text-amber-500 fill-amber-500" />
                    ) : (
                      <FileText size={14} className="text-primary-500" />
                    )}
                    <span className="font-semibold text-sm text-neutral-main">{tpl.name}</span>
                    {tpl.recommended && (
                      <span className="px-1.5 py-0.5 text-[10px] bg-amber-100 text-amber-700 rounded font-medium">추천</span>
                    )}
                    <span className="ml-auto text-[11px] text-neutral-muted">
                      {tpl.is_system ? '기본' : '커스텀'}
                    </span>
                  </div>
                  {tpl.field_labels?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {tpl.field_labels.map((label, i) => (
                        <span key={i} className="px-1.5 py-0.5 text-[11px] bg-primary-50 text-primary-700 rounded">
                          {label}
                        </span>
                      ))}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      );
    }

    case 'compound': {
      return <CompoundCard data={data} onSend={onSelectClarify} />;
    }

    case 'doc_pick': {
      const documents = data.documents || [];
      // 이 assistant 메시지 바로 앞의 user 메시지가 원본 쿼리
      const originalQuery = index > 0 ? (messages[index - 1]?.content || '요약해줘') : '요약해줘';
      return (
        <div>
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed">
            {data.message || '요약할 문서를 선택해주세요:'}
          </div>
          {documents.length > 0 && (
            <div className="mt-2 flex flex-col gap-2 max-h-64 overflow-y-auto pr-1">
              {documents.map((doc, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    useChatStore.getState().setSelectedDocument(doc.document_id, doc.title);
                    onSelectClarify?.(`${doc.title} 요약해줘`, { forceIntent: 'doc_retrieve:summary', documentId: doc.document_id });
                  }}
                  className="flex items-center gap-2 px-4 py-2.5 text-sm bg-surface-card border border-neutral-border rounded-xl hover:bg-primary-50 hover:border-primary-300 text-neutral-main hover:text-primary-700 transition text-left"
                >
                  <FileText size={14} className="flex-shrink-0 text-neutral-muted" />
                  <span className="truncate">{doc.title}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      );
    }

    case 'clarify': {
      const candidates = data.candidates || [];
      const clarifyFields = data.fields || [];
      // 이 assistant 메시지 바로 앞의 user 메시지가 원본 쿼리
      const originalQuery = index > 0 ? (messages[index - 1]?.content || '') : '';
      return (
        <div>
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-normal">
            <p>{content || data.message || '질문을 명확히 해주세요.'}</p>
            {clarifyFields.length > 0 && (
              <div className="mt-3">
                <p className="text-xs text-neutral-muted mb-2">필요한 정보</p>
                <div className="flex flex-wrap gap-1.5">
                  {clarifyFields.map((field, idx) => (
                    <span key={idx} className="px-2 py-1 text-xs bg-primary-50 text-primary-700 rounded-lg font-medium">
                      {field}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {data.example && (
              <p className="mt-3 text-xs text-neutral-muted">예시: "{data.example}"</p>
            )}
          </div>
          {candidates.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {candidates.map((c, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectClarify?.(originalQuery || c.query || c.label, { forceIntent: c.intent, silent: true })}
                  className="px-3 py-1.5 text-xs bg-primary-50 text-primary-700 rounded-full border border-primary-200 hover:bg-primary-100 transition"
                >
                  {typeof c === 'string' ? c : c.label || c.query}
                </button>
              ))}
            </div>
          )}
        </div>
      );
    }

    default: {
      const alreadyHasGuide = messages.some(m => m.role === 'assistant' && m.content === USAGE_GUIDE_TEXT);
      const prevUserMsg = messages.slice(0, index).reverse().find(m => m.role === 'user');
      const isGreeting = prevUserMsg && /^(안녕|하이|hello|hi)|사용법|도움말|뭐.*할.*수|어떻게.*써/i.test(prevUserMsg.content?.trim());
      const GREETING_TEXT = '안녕하세요! 듀드입니다.\n오늘도 업무에 도움이 필요하신가요?\n궁금한 점이나 요청 사항을 말씀해 주세요.';
      // 일반 응답: 문단 간격 없이 줄바꿈만 유지
      const cleanContent = content ? content.replace(/\(?\s*업무와\s*관련된\s*질문만\s*부탁드립니다\.?\s*\)?\s*\n?/g, '').replace(/\n+/g, '  \n').trim() : content;
      const displayContent = isGreeting ? GREETING_TEXT : cleanContent;
      return (
        <div>
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-line">
            {displayContent}
            {!alreadyHasGuide && isGreeting && (
              <>
                <p className="mt-4 text-neutral-sub text-sm">사용법이 궁금하시면 아래 <strong>사용법</strong> 버튼을 눌러주세요.</p>
                <button
                  onClick={() => useChatStore.getState().addMessage({ role: 'assistant', content: USAGE_GUIDE_TEXT })}
                  className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-full border border-primary-300 bg-primary-50 text-primary-700 text-xs font-semibold hover:bg-primary-100 transition"
                >
                  <HelpCircle size={14} />
                  사용법
                </button>
              </>
            )}
          </div>
          {/* 규정 경고 (schedule_add 하위 분기: pipeline, approval 등) */}
          {data.regulation_check && data.regulation_check.result && data.regulation_check.result !== 'no_regulation' && (
            <div className={`mt-2 rounded-lg p-3 border text-xs ${
              data.regulation_check.result === 'no' ? 'bg-red-50 border-red-200 text-red-700' :
              data.regulation_check.result === 'conditional' ? 'bg-yellow-50 border-yellow-200 text-yellow-700' :
              'bg-green-50 border-green-200 text-green-700'
            }`}>
              <div className="flex items-center gap-1.5 mb-1">
                <AlertTriangle size={13} />
                <span className="font-semibold">
                  {data.regulation_check.result === 'no' ? '규정 위반' : data.regulation_check.result === 'conditional' ? '조건부 허용' : '규정 부합'}
                </span>
              </div>
              {data.regulation_check.reason && <p>{data.regulation_check.reason}</p>}
              {data.regulation_check.regulation && <p className="mt-0.5 italic opacity-75">근거: {data.regulation_check.regulation}</p>}
            </div>
          )}
          {Array.isArray(data.warnings) && data.warnings.length > 0 && !data.regulation_check?.result && (
            <div className="mt-2 space-y-1">
              {data.warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-1.5 text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2">
                  <AlertTriangle size={13} className="text-yellow-500 mt-0.5 shrink-0" />
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }
  }
}

export default function ChatPage() {
  const [searchParams] = useSearchParams();
  const { messages, isStreaming, currentIntent, currentStatus, sendMessage } = useChat();
  const clearMessages = useChatStore((s) => s.clearMessages);
  const initSession = useChatStore((s) => s.initSession);
  const switchSession = useChatStore((s) => s.switchSession);
  const startNewSession = useChatStore((s) => s.startNewSession);
  const pendingQuestion = useChatStore((s) => s.pendingQuestion);
  const clearPendingQuestion = useChatStore((s) => s.clearPendingQuestion);
  const selectedDocumentId = useChatStore((s) => s.selectedDocumentId);
  const selectedDocumentName = useChatStore((s) => s.selectedDocumentName);
  const setSelectedDocument = useChatStore((s) => s.setSelectedDocument);
  const clearSelectedDocument = useChatStore((s) => s.clearSelectedDocument);
  const addMessage = useChatStore((s) => s.addMessage);
  const [panelOpen, setPanelOpen] = useState(false);
  const [docViewDoc, setDocViewDoc] = useState(null);
  const [sessionSidebarOpen, setSessionSidebarOpen] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [lastInput, setLastInput] = useState('');
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [dbRegulations, setDbRegulations] = useState([]);
  const [docPickerOpen, setDocPickerOpen] = useState(false);
  const [docList, setDocList] = useState([]);
  const [docSearch, setDocSearch] = useState('');
  const [hasNewRegulations, setHasNewRegulations] = useState(false);
  const [isHeaderHidden, setIsHeaderHidden] = useState(false);

  const mountedRef = useRef(false);
  const lastSeenJudgmentIdxRef = useRef(-1);

  // Cmd+B (Mac) / Ctrl+B (기타) → 대화 목록 사이드바 토글
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        setSessionSidebarOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;

    const sessionParam = searchParams.get('session');
    const q = useChatStore.getState().pendingQuestion;
    if (sessionParam) {
      // URL에서 세션 ID로 직접 전환 (마이페이지 등에서 클릭)
      switchSession(sessionParam);
    } else if (q) {
      // 대시보드에서 질문 클릭 → 새 세션 시작 후 자동 전송 (세션은 sendMessage에서 생성)
      clearPendingQuestion();
      setLastInput(q);
      sendMessage(q);
    } else {
      // 페이지 진입 시 즉시 새 대화창으로 초기화 (이전 대화 안 보이게)
      startNewSession();
      initSession();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    listRegulations()
      .then((res) => setDbRegulations(res.data || []))
      .catch((err) => console.warn('[ChatPage] 규정 로드 실패:', err));
  }, []);

  useEffect(() => {
    if (!docPickerOpen) return;
    listDocuments()
      .then((res) => setDocList(res.data?.documents || res.data || []))
      .catch((err) => console.warn('[ChatPage] 문서 로드 실패:', err));
  }, [docPickerOpen]);

  const handleSend = async (text, filesOrOptions = []) => {
    const storeState = useChatStore.getState();

    // 후속 액션 버튼에서 options 객체로 호출된 경우 (forceIntent 포함)
    // isStreaming 체크를 건너뜀 — doc_pick, 액션 버튼은 스트리밍 중에도 허용
    if (filesOrOptions && !Array.isArray(filesOrOptions) && typeof filesOrOptions === 'object') {
      const options = filesOrOptions;
      setLastError(null);
      setLastInput(text);
      sendMessage(text, options);
      return;
    }

    if (storeState.isStreaming) return; // 일반 전송 중복 방지

    setLastError(null);
    setLastInput(text);

    // 파일 업로드 처리
    const files = filesOrOptions;
    if (files && files.length > 0) {
      const storeState = useChatStore.getState();
      storeState.setStreaming(true);
      storeState.setCurrentStatus('문서 업로드 및 문서 구조 분석 중...');
      try {
        const file = files[0];
        const res = await uploadDocument(file, 'personal');
        storeState.setSelectedDocument(res.data.id, res.data.title);
      } catch (err) {
        console.error('[ChatPage] 파일 업로드 실패:', err);
        setLastError('파일 업로드에 실패했습니다. 다시 시도해주세요.');
        storeState.setStreaming(false);
        storeState.setCurrentStatus(null);
        return;
      }
      storeState.setCurrentStatus(null);
      storeState.setStreaming(false);
    }

    sendMessage(text);
  };

  const handleRetry = () => {
    if (lastInput) {
      setLastError(null);
      sendMessage(lastInput);
    }
  };

  const handleClear = () => {
    if (messages.length === 0) return;
    setShowClearConfirm(true);
  };

  const confirmClear = () => {
    clearMessages();
    setLastError(null);
    setLastInput('');
    setShowClearConfirm(false);
  };

  // 메시지에서 마지막 judgment 응답의 regulations 추출 (DB 원문 우선 병합)
  const regulationsFromMessages = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.resultIntent === 'judgment' && msg.agentResponse?.regulations) {
        const confidence = msg.agentResponse.confidence;
        return msg.agentResponse.regulations.map((r) => {
          const articleKey = (r.article || r.name || '').match(/제\d+조/)?.[0];
          const dbReg = articleKey
            ? dbRegulations.find((db) => db.article_number === articleKey)
            : null;
          const rawRelevance = r.relevance ?? r.score ?? null;
          const relevance = typeof rawRelevance === 'number' && !isNaN(rawRelevance)
            ? rawRelevance
            : (typeof confidence === 'number' && !isNaN(confidence) ? confidence : null);
          return {
            name: r.name || dbReg?.title || '',
            article: r.article || dbReg?.article_number || '',
            content: dbReg?.content || r.content || '',
            relevance,
          };
        });
      }
    }
    return [];
  }, [messages, dbRegulations]);

  // 판단 agent 응답으로 새 규정이 들어오면 알림 활성화
  useEffect(() => {
    let latestIdx = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].resultIntent === 'judgment' && messages[i].agentResponse?.regulations?.length > 0) {
        latestIdx = i;
        break;
      }
    }
    if (latestIdx > -1 && latestIdx !== lastSeenJudgmentIdxRef.current && !panelOpen) {
      setHasNewRegulations(true);
    }
  }, [messages, panelOpen]);

  return (
    <div className="flex flex-col h-full bg-surface-main">
      <header className="z-20 bg-surface-main relative border-b border-neutral-border shrink-0">
        <div className="flex justify-between items-center pl-8 pr-8 py-4">
          <div>
            <h1 className="font-bold text-xl">나에게 물어봐</h1>
            <p className="text-neutral-sub text-sm mt-0.5">규정 판단, 문서 분석, 일정 관리를 도와드립니다</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => exportChat(messages)}
              disabled={messages.length === 0}
              className="btn-outline text-xs disabled:opacity-40 disabled:cursor-not-allowed"
              title="대화 내보내기"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              내보내기
            </button>
            <button
              onClick={handleClear}
              disabled={messages.length === 0}
              className="btn-outline text-xs disabled:opacity-40 disabled:cursor-not-allowed text-red-500 border-red-200 hover:bg-red-50"
              title="대화 초기화"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
              초기화
            </button>
            <button
              onClick={() => setDocPickerOpen(true)}
              className={`btn-outline text-xs ${selectedDocumentId ? 'bg-accent-50 border-accent-300 text-accent-700' : ''}`}
              title="요약할 문서 선택"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              {selectedDocumentId ? '문서 선택됨' : '문서 선택'}
            </button>
            <button
              onClick={() => {
                const opening = !panelOpen;
                setPanelOpen(opening);
                if (opening) {
                  setHasNewRegulations(false);
                  for (let i = messages.length - 1; i >= 0; i--) {
                    if (messages[i].resultIntent === 'judgment' && messages[i].agentResponse?.regulations?.length > 0) {
                      lastSeenJudgmentIdxRef.current = i;
                      break;
                    }
                  }
                }
              }}
              className={`btn-outline text-xs relative ${panelOpen ? 'bg-primary-50 border-primary-300' : ''} ${hasNewRegulations && !panelOpen ? 'border-primary-400 bg-primary-50 text-primary-700 shadow-[0_0_8px_rgba(59,130,246,0.5)]' : ''}`}
              style={hasNewRegulations && !panelOpen ? { animation: 'reg-glow 1.5s ease-in-out infinite' } : undefined}
            >
              규정 패널
              {hasNewRegulations && !panelOpen && (
                <span className="absolute -top-1.5 -right-1.5 flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-primary-500"></span>
                </span>
              )}
            </button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* 왼쪽 아이콘 레일 + 세션 사이드바 */}
        <div className="flex flex-shrink-0 h-full relative z-10">
          <div className="w-16 flex flex-col items-center py-4 gap-4 bg-transparent sticky top-[86px] z-20">
            <button
              onClick={() => setSessionSidebarOpen(!sessionSidebarOpen)}
              title={sessionSidebarOpen ? '대화 목록 닫기' : '대화 목록'}
              className={`w-11 h-11 flex items-center justify-center rounded-full shadow-sm transition hover:shadow-md ${sessionSidebarOpen
                ? 'bg-primary-700 text-white'
                : 'bg-surface-card text-neutral-sub hover:text-neutral-main border border-neutral-border'
                }`}
            >
              <Menu size={20} />
            </button>
            <button
              onClick={() => { startNewSession(); setSessionSidebarOpen(false); setIsHeaderHidden(false); }}
              title="새 대화"
              className="w-11 h-11 flex items-center justify-center rounded-full bg-surface-card text-neutral-sub border border-neutral-border shadow-sm transition hover:shadow-md hover:text-neutral-main"
            >
              <MessageSquarePlus size={20} />
            </button>
          </div>
          <ChatSessionSidebar isOpen={sessionSidebarOpen} />
        </div>

        {/* 챗 영역 */}
        <div className="flex-1 min-w-0">
          <ChatWindow onSend={handleSend} messages={messages} selectedDocumentName={selectedDocumentName} onClearDocument={clearSelectedDocument} activeIntent={currentIntent || messages.filter(m => m.role === 'assistant').at(-1)?.resultIntent || messages.filter(m => m.role === 'assistant').at(-1)?.intent} isStreaming={isStreaming} panelOpen={panelOpen || !!docViewDoc} onScrollChange={setIsHeaderHidden}>
            {/* 메시지가 없을 때 — 추천 질문 */}
            {messages.length === 0 && (
              <SuggestedQuestions onSelect={handleSend} />
            )}

            {/* 메시지 렌더링 */}
            {messages.map((msg, i) => {
              const isLastAssistant = msg.role === 'assistant' && i === messages.length - 1 && isStreaming;
              // 빈 어시스턴트 메시지: isStreaming 설정 전에도 타이핑 인디케이터 표시
              const isWaitingForResponse = !isLastAssistant && msg.role === 'assistant' && i === messages.length - 1 && !msg.content && !msg.error && !msg.agentResponse;

              // 사용자 메시지
              if (msg.role === 'user') {
                return <MessageBubble key={i} type="user">{msg.content}</MessageBubble>;
              }

              // 에러 메시지
              if (msg.error) {
                return <ErrorMessage key={i} message={msg.error} onRetry={handleRetry} />;
              }

              // 스트리밍 중이지만 result가 이미 도착한 경우 → 카드 UI로 바로 전환
              if ((isLastAssistant || isWaitingForResponse) && !(msg.agentResponse && msg.resultIntent)) {
                const intent = msg.resultIntent || msg.intent || currentIntent || 'general';
                const subType = useChatStore.getState().currentSubType;

                // QA: 카드 스켈레톤 안에서 텍스트 스트리밍 (날것 → 카드 전환 방지)
                if (intent === 'doc_retrieve' && subType === 'qa' && msg.content) {
                  const partialMsg = {
                    ...msg,
                    resultIntent: 'doc_retrieve',
                    agentResponse: { sub_type: 'qa', confidence: null },
                  };
                  return (
                    <MessageBubble key={i} type="bot" intent={intent}>
                      {renderCardMessage(partialMsg, handleSend, setDocViewDoc, messages, i, true)}
                    </MessageBubble>
                  );
                }

                // 요약/검색: 로딩만 표시 (메타데이터 노출 방지)
                // 일반/판단: 실시간 스트리밍 텍스트
                const hideStreamText = ['doc_retrieve', 'doc_search', 'doc_summary'].includes(intent);
                return (
                  <MessageBubble key={i} type="bot" intent={intent}>
                    <StreamingMessage
                      text={hideStreamText ? '' : (intent === 'judgment' ? cleanResultText(msg.content) : msg.content)}
                      status={currentStatus || (hideStreamText && msg.content ? '문서 응답 생성 중...' : null)}
                      intent={intent}
                      isInsideBubble
                      isStreaming={isLastAssistant || isWaitingForResponse}
                    />
                  </MessageBubble>
                );
              }

              // AI 완료 또는 result 도착 — agentResponse 카드 렌더링
              if (msg.agentResponse && msg.resultIntent) {
                return (
                  <MessageBubble key={i} type="bot" intent={msg.resultIntent || msg.intent} modelName={msg.agentResponse?.model_name}>
                    {renderCardMessage(msg, handleSend, setDocViewDoc, messages, i, isStreaming && i === messages.length - 1)}
                  </MessageBubble>
                );
              }

              // AI 완료 — 기본 텍스트 버블
              // "안녕하세요" 인사일 때만 사용법 버튼 표시
              const prevUser = messages.slice(0, i).reverse().find(m => m.role === 'user');
              const isGreetingMsg = prevUser && /^(안녕|하이|hello|hi)|사용법|도움말|뭐.*할.*수|어떻게.*써/i.test(prevUser.content?.trim());
              const cleanedContent = msg.content ? msg.content.replace(/\n{2,}/g, '\n') : msg.content;
              return (
                <MessageBubble key={i} type="bot" intent={msg.intent} modelName={msg.agentResponse?.model_name}>
                  <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed">
                    <MarkdownText>{cleanedContent}</MarkdownText>
                    {!messages.some(m => m.role === 'assistant' && m.content === USAGE_GUIDE_TEXT) && isGreetingMsg && (
                      <>
                        <p className="mt-2 text-neutral-sub text-sm">사용법이 궁금하시면 아래 <strong>사용법</strong> 버튼을 눌러주세요.</p>
                        <button
                          onClick={() => addMessage({ role: 'assistant', content: USAGE_GUIDE_TEXT })}
                          className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-full border border-primary-300 bg-primary-50 text-primary-700 text-xs font-semibold hover:bg-primary-100 transition"
                        >
                          <HelpCircle size={14} />
                          사용법
                        </button>
                      </>
                    )}
                  </div>
                </MessageBubble>
              );
            })}

            {/* 에러 표시 */}
            {lastError && <ErrorMessage message={lastError} onRetry={handleRetry} />}
          </ChatWindow>
        </div>

        {/* 우측 패널: 문서 보기 or 규정 패널 */}
        {docViewDoc ? (
          <DocumentViewPanel doc={docViewDoc} onClose={() => setDocViewDoc(null)} />
        ) : (
          <RegulationPanel
            regulations={regulationsFromMessages}
            isOpen={panelOpen}
            onClose={() => setPanelOpen(false)}
          />
        )}
      </div>

      {/* 문서 선택 피커 */}
      {docPickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => { setDocPickerOpen(false); setDocSearch(''); }}>
          <div className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-xl shadow-xl w-[28rem] max-w-[90vw] overflow-hidden border border-white/40 dark:border-white/10" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-divider">
              <h3 className="text-sm font-semibold text-neutral-main">요약할 문서 선택</h3>
              <button onClick={() => { setDocPickerOpen(false); setDocSearch(''); }} className="text-neutral-muted hover:text-neutral-main transition">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="px-4 py-3 border-b border-neutral-divider">
              <input
                autoFocus
                value={docSearch}
                onChange={(e) => setDocSearch(e.target.value)}
                placeholder="문서 검색..."
                className="w-full px-3 py-2 text-sm border border-neutral-border rounded-md bg-surface-main outline-none focus:border-primary-300 text-neutral-main placeholder:text-neutral-muted"
              />
            </div>
            <div className="max-h-64 overflow-y-auto py-1">
              {docList.filter(d => !docSearch || d.title?.includes(docSearch) || d.original_filename?.includes(docSearch)).length === 0 ? (
                <div className="py-8 text-center text-sm text-neutral-muted">
                  {docList.length === 0 ? '등록된 문서가 없습니다' : '검색 결과 없음'}
                </div>
              ) : (
                docList
                  .filter(d => !docSearch || d.title?.includes(docSearch) || d.original_filename?.includes(docSearch))
                  .map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => { setSelectedDocument(doc.id, doc.title || doc.original_filename); setDocPickerOpen(false); setDocSearch(''); }}
                      className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-hover transition text-sm ${selectedDocumentId === doc.id ? 'bg-accent-50 text-accent-700' : 'text-neutral-main'}`}
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0 text-neutral-muted">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                      <span className="truncate">{doc.title || doc.original_filename}</span>
                    </button>
                  ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* 대화 초기화 확인 */}
      {showClearConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-xl shadow-xl p-6 max-w-sm w-full mx-4 border border-white/40 dark:border-white/10">
            <h3 className="text-base font-semibold mb-2">대화 기록을 초기화할까요?</h3>
            <p className="text-sm text-neutral-sub mb-5">모든 대화 내용이 삭제됩니다. 이 작업은 되돌릴 수 없습니다.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowClearConfirm(false)} className="btn-outline text-sm px-4 py-2">취소</button>
              <button onClick={confirmClear} className="bg-red-500 hover:bg-red-600 text-white text-sm px-4 py-2 rounded-md transition">삭제</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
