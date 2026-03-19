import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Check, X, Clock, Coffee, GitPullRequest, FileText, FileSignature,
    Filter, Search, BellRing, CheckCircle2, XCircle, Trash2, Paperclip,
    Home, DoorOpen, Palette, Award, Receipt, Rocket, Server, ShieldCheck, RefreshCw,
    Sparkles, ArrowRight, Zap, Plus, CheckSquare, Square, ListChecks,
    CalendarPlus, CalendarClock, Download, Eye, Send, User, FolderOpen, Pencil
} from 'lucide-react';
import { listApprovals, createApproval, approveRequest, rejectRequest, deleteApproval, updateApproval, suggestApprovals, downloadApprovalFile, getApprovalFileBlobUrl } from '../../api/approvals';
import { createSchedule } from '../../api/schedules';
import { listPipelineTasks } from '../../api/tasks';
import { getAllMembers } from '../../api/auth';
import client from '../../api/client';
import useAuthStore from '../../store/authStore';
import MemberDropdown from '../common/MemberDropdown';
import DatePicker from '../common/DatePicker';

const TEAMS = ['개발', 'QA기획', 'UI/UX', '영업', '마케팅', 'CS'];

const typeConfig = {
    leave: { icon: Coffee, color: 'text-accent-700 bg-accent-50', label: '연차/반차 신청' },
    remote: { icon: Home, color: 'text-primary-700 bg-primary-50', label: '재택근무 신청' },
    room: { icon: DoorOpen, color: 'text-primary-500 bg-primary-50', label: '회의실 예약' },
    design: { icon: Palette, color: 'text-accent-500 bg-accent-50', label: '디자인 에셋 요청' },
    certificate: { icon: Award, color: 'text-warning bg-warning-bg', label: '증명서 발급 요청' },
    budget: { icon: Receipt, color: 'text-primary-900 bg-primary-50', label: '결재 요청' },
    review: { icon: GitPullRequest, color: 'text-info bg-info-bg', label: 'PR 리뷰 요청' },
    deploy: { icon: Rocket, color: 'text-success bg-success-bg', label: '배포 승인 요청' },
    infra: { icon: Server, color: 'text-neutral-sub bg-surface-sub', label: '인프라/권한 신청' },
    security: { icon: ShieldCheck, color: 'text-error bg-error-bg', label: '보안 예외 처리' },
    other: { icon: FileSignature, color: 'text-neutral-muted bg-surface-sub', label: '기타' },
};
const defaultTypeConfig = { icon: FileSignature, color: 'text-neutral-muted bg-surface-sub', label: '요청' };

const statusBadge = {
    pending: { label: '대기중', color: 'bg-info-bg text-info border-primary-100', dot: 'bg-info' },
    approved: { label: '승인됨', color: 'bg-success-bg text-success border-success-bg', dot: 'bg-success' },
    rejected: { label: '거절됨', color: 'bg-error-bg text-error border-error-bg', dot: 'bg-error' },
};

const priorityBadge = {
    high: 'bg-error-bg text-error',
    medium: 'bg-warning-bg text-warning',
    low: 'bg-success-bg text-success',
};

const scheduleTypeConfig = {
    meeting: { color: 'bg-primary-50 text-primary-700', label: '회의' },
    task: { color: 'bg-info-bg text-info', label: '작업' },
    deadline: { color: 'bg-error-bg text-error', label: '마감' },
    review: { color: 'bg-warning-bg text-warning', label: '리뷰' },
    milestone: { color: 'bg-success-bg text-success', label: '마일스톤' },
};

/** suggested_day → 실제 날짜 변환 */
function resolveSuggestedDay(day) {
    const now = new Date();
    if (!day || day === 'today') {
        return now;
    }
    if (day === 'tomorrow') {
        const d = new Date(now);
        d.setDate(d.getDate() + 1);
        return d;
    }
    if (day === 'this_week') {
        const d = new Date(now);
        d.setDate(d.getDate() + 2);
        return d;
    }
    // YYYY-MM-DD
    const parsed = new Date(day);
    return isNaN(parsed.getTime()) ? now : parsed;
}

export default function ApprovalPanel({ onReady, externalActions, onScheduleAdded }) {
    const user = useAuthStore((s) => s.user);
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [formData, setFormData] = useState({ type: 'leave', title: '', detail: '', target_team: '', target_user_id: '', customType: '' });
    const [formFile, setFormFile] = useState(null);
    const [submitting, setSubmitting] = useState(false);
    const [allMembers, setAllMembers] = useState([]);
    const [suggestions, setSuggestions] = useState([]);
    const [suggestLoading, setSuggestLoading] = useState(false);
    const [suggestContext, setSuggestContext] = useState(null);
    const [suggestError, setSuggestError] = useState(null);
    const [deleteConfirm, setDeleteConfirm] = useState(null);
    const [selectedSent, setSelectedSent] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);
    const [editMode, setEditMode] = useState(false);
    const [editTitle, setEditTitle] = useState('');
    const [editDetail, setEditDetail] = useState('');
    const [editSaving, setEditSaving] = useState(false);
    const [pipelineTasks, setPipelineTasks] = useState([]);

    // Schedule checklist state
    const [checklist, setChecklist] = useState([]);
    const [checklistLoading, setChecklistLoading] = useState(false);
    const [checklistError, setChecklistError] = useState(null);

    // Schedule suggestions state
    const [scheduleSuggestions, setScheduleSuggestions] = useState([]);
    const [schedSuggestLoading, setSchedSuggestLoading] = useState(false);
    const [schedSuggestError, setSchedSuggestError] = useState(null);
    const [addingScheduleId, setAddingScheduleId] = useState(null);

    // Date picker modal for schedule suggestions
    const [schedulePickerData, setSchedulePickerData] = useState(null); // { suggestion, idx }
    const [pickerTitle, setPickerTitle] = useState('');
    const [pickerDate, setPickerDate] = useState('');
    const [pickerStartTime, setPickerStartTime] = useState('10:00');
    const [pickerEndTime, setPickerEndTime] = useState('11:00');
    const [pickerAllDay, setPickerAllDay] = useState(false);
    const [pickerScheduleType, setPickerScheduleType] = useState('meeting');
    const [pickerShareScope, setPickerShareScope] = useState('project'); // 'team' | 'project'
    const [pickerGoogleMeet, setPickerGoogleMeet] = useState(false);
    const [pickerAttendees, setPickerAttendees] = useState('');  // comma-separated emails

    // Schedule result modal (success / failure)
    const [scheduleResult, setScheduleResult] = useState(null); // { success: bool, title: string, message: string }

    // New Tasks tab: 'approvals' | 'schedules'
    const [newTasksTab, setNewTasksTab] = useState('approvals');

    // LLM model info for debugging
    const [suggestModelInfo, setSuggestModelInfo] = useState(null);
    const [schedModelInfo, setSchedModelInfo] = useState(null);

    const loadAll = async () => {
        setLoading(true);
        try {
            const [pendingRes, approvedRes, rejectedRes, myPendingRes] = await Promise.all([
                client.get('/approvals/', { params: { status: 'pending' } }).catch(() => ({ data: [] })),
                client.get('/approvals/history', { params: { status: 'approved' } }).catch(() => ({ data: [] })),
                client.get('/approvals/history', { params: { status: 'rejected' } }).catch(() => ({ data: [] })),
                client.get('/approvals/history', { params: { status: 'pending' } }).catch(() => ({ data: [] })),
            ]);
            const raw = [
                ...(Array.isArray(pendingRes.data) ? pendingRes.data : []),
                ...(Array.isArray(approvedRes.data) ? approvedRes.data : []),
                ...(Array.isArray(rejectedRes.data) ? rejectedRes.data : []),
                ...(Array.isArray(myPendingRes.data) ? myPendingRes.data : []),
            ];
            // Deduplicate by id
            const seen = new Set();
            const all = raw.filter(item => {
                if (seen.has(item.id)) return false;
                seen.add(item.id);
                return true;
            });
            setItems(all);
        } catch {
            setItems([]);
        } finally {
            setLoading(false);
        }
    };

    const loadChecklist = async () => {
        setChecklistLoading(true);
        setChecklistError(null);
        try {
            const res = await client.post('/approvals/checklist');
            const items = res.data?.checklist || [];

            const saved = JSON.parse(localStorage.getItem('schedule_checklist') || '{}');
            const withState = items.map((item, idx) => ({
                id: `chk-${idx}-${item.title?.slice(0, 10)}`,
                title: item.title,
                category: item.category || 'task',
                priority: item.priority || 'medium',
                due: item.due || '',
                related: item.related || '',
                done: saved[`chk-${idx}-${item.title?.slice(0, 10)}`] || false,
            }));

            setChecklist(withState);
        } catch (err) {
            const status = err.response?.status;
            const detail = err.response?.data?.detail || err.message || '알 수 없는 오류';
            console.error('Checklist load failed:', status, detail, err);
            setChecklistError(`${status || 'ERR'}: ${detail}`);
            setChecklist([]);
        } finally {
            setChecklistLoading(false);
        }
    };

    const loadScheduleSuggestions = async () => {
        setSchedSuggestLoading(true);
        setScheduleSuggestions([]);
        setSchedSuggestError(null);
        setSchedModelInfo(null);
        try {
            const res = await client.post('/approvals/suggest-schedules', {}, { timeout: 180000 });
            setScheduleSuggestions(res.data?.suggestions || []);
            if (res.data?.model_info) setSchedModelInfo(res.data.model_info);
        } catch (err) {
            const status = err.response?.status;
            const detail = err.response?.data?.detail || err.message || '알 수 없는 오류';
            console.error('일정 추천 실패:', status, detail);
            setSchedSuggestError(`${status || 'ERR'}: ${detail}`);
        } finally {
            setSchedSuggestLoading(false);
        }
    };

    useEffect(() => {
        loadAll();
        loadChecklist();
        getAllMembers().then(res => setAllMembers(res.data || [])).catch(() => {});
        listPipelineTasks().then(res => setPipelineTasks(Array.isArray(res.data) ? res.data : [])).catch(() => {});
    }, []);

    useEffect(() => {
        if (onReady && externalActions) {
            onReady({
                refresh: () => { loadAll(); loadChecklist(); if (newTasksTab === 'schedules') loadScheduleSuggestions(); else handleSuggest(); },
                openCreate: () => {
                    setFormData({ type: 'leave', title: '', detail: '', target_team: '', target_user_id: '', customType: '' });
                    setShowModal(true);
                },
                loading
            });
        }
    }, [onReady, externalActions, loading]);

    const handleApproval = async (id, approve) => {
        try {
            if (approve) await approveRequest(id);
            else await rejectRequest(id);
            await loadAll();
        } catch (err) {
            console.error('Action failed', err);
        }
    };

    const handleDeleteClick = (item) => {
        setDeleteConfirm({ id: item.id, title: item.title });
    };

    const handleDeleteConfirm = async () => {
        if (!deleteConfirm) return;
        try {
            await deleteApproval(deleteConfirm.id);
            setDeleteConfirm(null);
            await loadAll();
        } catch (err) {
            const msg = err.response?.data?.detail || '삭제에 실패했습니다.';
            alert(msg);
            setDeleteConfirm(null);
        }
    };

    const timeAgo = (dateStr) => {
        if (!dateStr) return '';
        const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
        if (diff < 60) return '방금 전';
        if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
        return `${Math.floor(diff / 86400)}일 전`;
    };

    const openSentDetail = async (item) => {
        setSelectedSent(item);
        setPreviewUrl(null);
        if (item.file_name) {
            try {
                const url = await getApprovalFileBlobUrl(item.id, item.file_name);
                setPreviewUrl(url);
            } catch { }
        }
    };

    const closeSentDetail = () => {
        if (previewUrl) window.URL.revokeObjectURL(previewUrl);
        setSelectedSent(null);
        setPreviewUrl(null);
        setEditMode(false);
    };

    const startEdit = () => {
        setEditTitle(selectedSent.title);
        setEditDetail(selectedSent.detail || '');
        setEditMode(true);
    };

    const saveEdit = async () => {
        if (!selectedSent || !editTitle.trim()) return;
        setEditSaving(true);
        try {
            await updateApproval(selectedSent.id, { title: editTitle.trim(), detail: editDetail.trim() });
            setSelectedSent({ ...selectedSent, title: editTitle.trim(), detail: editDetail.trim() });
            setEditMode(false);
            await loadAll();
        } catch (err) {
            alert(err.response?.data?.detail || '수정에 실패했습니다.');
        } finally {
            setEditSaving(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!formData.title.trim()) return;
        if (!formData.target_user_id) {
            alert('보낼 팀원을 선택해주세요.');
            return;
        }
        setSubmitting(true);
        try {
            await createApproval({
                type: formData.type === 'other' ? (formData.customType.trim() || 'other') : formData.type,
                title: formData.title.trim(),
                detail: formData.detail.trim() || null,
                target_team: formData.target_team || null,
                target_user_id: formData.target_user_id || null,
            }, formFile);
            setShowModal(false);
            setFormData({ type: 'leave', title: '', detail: '', target_team: '', target_user_id: '', customType: '' });
            setFormFile(null);
            // Remove the applied suggestion from New Tasks
            if (appliedSuggestionIdx !== null) {
                setSuggestions(prev => prev.filter((_, i) => i !== appliedSuggestionIdx));
                setAppliedSuggestionIdx(null);
            }
            await loadAll();
        } catch {
            alert('요청 생성에 실패했습니다.');
        } finally {
            setSubmitting(false);
        }
    };

    const handleSuggest = async () => {
        setSuggestLoading(true);
        setSuggestions([]);
        setSuggestError(null);
        setSuggestModelInfo(null);
        try {
            const res = await suggestApprovals();
            setSuggestions(res.data?.suggestions || []);
            setSuggestContext(res.data?.context || null);
            if (res.data?.model_info) setSuggestModelInfo(res.data.model_info);
        } catch (err) {
            const status = err.response?.status;
            const detail = err.response?.data?.detail || err.message || '알 수 없는 오류';
            console.error('AI 추천 실패:', status, detail);
            setSuggestError(`${status || 'ERR'}: ${detail}`);
            setSuggestions([]);
        } finally {
            setSuggestLoading(false);
        }
    };

    const [appliedSuggestionIdx, setAppliedSuggestionIdx] = useState(null);

    const applySuggestion = (s, idx) => {
        setFormData({ type: s.type, title: s.title, detail: s.detail || '', target_team: '', target_user_id: '', customType: '' });
        setAppliedSuggestionIdx(idx);
        setShowModal(true);
    };

    /** 날짜 선택 모달 열기 */
    const openSchedulePicker = (s, idx) => {
        const defaultDate = resolveSuggestedDay(s.suggested_day);
        const yyyy = defaultDate.getFullYear();
        const mm = String(defaultDate.getMonth() + 1).padStart(2, '0');
        const dd = String(defaultDate.getDate()).padStart(2, '0');
        setPickerDate(`${yyyy}-${mm}-${dd}`);
        const duration = s.duration_minutes || 60;
        setPickerStartTime('10:00');
        const endH = Math.floor((600 + duration) / 60);
        const endM = (600 + duration) % 60;
        setPickerEndTime(`${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`);
        setPickerTitle(s.title);
        setPickerAllDay(false);
        setPickerScheduleType(s.schedule_type || 'meeting');
        setPickerShareScope('project');
        setPickerGoogleMeet(false);
        setPickerAttendees('');
        setSchedulePickerData({ suggestion: s, idx });
    };

    /** 추천 일정을 캘린더에 추가 (날짜 선택 후 확정) */
    const confirmAddSchedule = async () => {
        if (!schedulePickerData || !pickerDate) return;
        const { suggestion: s, idx } = schedulePickerData;
        setAddingScheduleId(idx);
        try {
            // 타임존 없는 로컬 시간 문자열 (DB: TIMESTAMP WITHOUT TIME ZONE)
            let startStr, endStr;
            if (pickerAllDay) {
                startStr = `${pickerDate}T00:00:00`;
                endStr = `${pickerDate}T23:59:59`;
            } else {
                startStr = `${pickerDate}T${pickerStartTime}:00`;
                endStr = `${pickerDate}T${pickerEndTime}:00`;
            }

            if (isNaN(new Date(startStr).getTime()) || isNaN(new Date(endStr).getTime())) {
                setScheduleResult({ success: false, title: '', message: '유효한 날짜와 시간을 입력해주세요.' });
                setAddingScheduleId(null);
                return;
            }

            const addedTitle = pickerTitle.trim() || s.title;
            const attendeeList = pickerAttendees
                .split(',')
                .map(e => e.trim())
                .filter(e => e.includes('@'));

            await createSchedule({
                title: addedTitle,
                description: s.description || s.reason || '',
                start_time: startStr,
                end_time: endStr,
                schedule_type: pickerScheduleType,
                priority: s.priority || 'medium',
                create_meet: pickerGoogleMeet,
                share_scope: pickerShareScope,
                attendees: attendeeList.length > 0 ? attendeeList : undefined,
            });

            // 추가 성공 → 해당 항목 제거 & 모달 닫기 & 캘린더 새로고침
            setScheduleSuggestions(prev => prev.filter((_, i) => i !== idx));
            setSchedulePickerData(null);
            setScheduleResult({ success: true, title: addedTitle, message: `"${addedTitle}" 일정이 캘린더에 추가되었습니다.` });
            if (onScheduleAdded) onScheduleAdded();
        } catch (err) {
            const detail = err.response?.data?.detail || '캘린더 추가에 실패했습니다.';
            setScheduleResult({ success: false, title: '', message: typeof detail === 'string' ? detail : '캘린더 추가에 실패했습니다.' });
        } finally {
            setAddingScheduleId(null);
        }
    };

    const toggleCheckItem = (itemId) => {
        setChecklist(prev => {
            const updated = prev.map(c => c.id === itemId ? { ...c, done: !c.done } : c);
            const saved = {};
            updated.forEach(c => { saved[c.id] = c.done; });
            localStorage.setItem('schedule_checklist', JSON.stringify(saved));
            return updated;
        });
    };

    // Load initial suggestions based on active tab
    useEffect(() => { handleSuggest(); }, []);

    /* ── Pending 카드 (받은 요청) ── */
    const renderPendingCard = (item) => {
        const cfg = typeConfig[item.type] || defaultTypeConfig;
        const IconComp = cfg.icon;
        return (
            <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className="bg-white dark:bg-neutral-800 p-4 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] transition-all group"
            >
                <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-2">
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${cfg.color}`}>
                            <IconComp size={14} />
                        </div>
                        <span className="text-[11px] font-semibold text-neutral-muted">{cfg.label}</span>
                    </div>
                    <button
                        onClick={() => handleDeleteClick(item)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-error-bg text-neutral-muted hover:text-error transition-all"
                        title="삭제"
                    >
                        <Trash2 size={12} />
                    </button>
                </div>
                <h4 className="text-[13px] font-bold text-neutral-main leading-snug mb-1 line-clamp-2">{item.title}</h4>
                {item.detail && (
                    <p className="text-[11px] text-neutral-muted line-clamp-2 mb-3">{item.detail}</p>
                )}
                <div className="flex items-center gap-2 pt-2.5 border-t border-neutral-divider dark:border-neutral-border">
                    {item.requester_avatar ? (
                        <img src={item.requester_avatar} alt="" className="w-7 h-7 rounded-full object-cover ring-2 ring-white dark:ring-neutral-800" />
                    ) : (
                        <div className="w-7 h-7 rounded-full bg-primary-100 dark:bg-primary-50 flex items-center justify-center text-[11px] font-bold text-primary-700">
                            {(item.requester_name || '?')[0]}
                        </div>
                    )}
                    <span className="text-[11px] font-medium text-neutral-sub truncate">{item.requester_name || '알 수 없음'}</span>
                    {item.created_at && (
                        <span className="text-[10px] text-neutral-muted ml-auto shrink-0">
                            {timeAgo(item.created_at)}
                        </span>
                    )}
                </div>
                {item.file_name && (
                    <div className="flex items-center gap-1 mt-2 text-[10px] text-neutral-muted">
                        <Paperclip size={10} className="text-neutral-muted" />
                        <span className="truncate">{item.file_name}</span>
                    </div>
                )}
                <div className="flex gap-2 mt-3">
                    <button
                        onClick={() => handleApproval(item.id, true)}
                        className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-primary-50 hover:bg-primary-700 text-primary-700 hover:text-white text-[11px] font-semibold rounded-lg transition-all"
                    >
                        <Check size={12} /> Approve
                    </button>
                    <button
                        onClick={() => handleApproval(item.id, false)}
                        className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-error-bg hover:bg-error text-error hover:text-white text-[11px] font-semibold rounded-lg transition-all"
                    >
                        <X size={12} /> Reject
                    </button>
                </div>
            </motion.div>
        );
    };

    /* ── Sent 카드 (보낸 요청 - Pending/Approved/Rejected) ── */
    const renderSentCard = (item) => {
        const cfg = typeConfig[item.type] || defaultTypeConfig;
        const IconComp = cfg.icon;
        const isApproved = item.status === 'approved';
        const isPending = item.status === 'pending';
        const cardBg = 'bg-white/40 dark:bg-neutral-800/40';
        return (
            <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                onClick={() => openSentDetail(item)}
                className={`${cardBg} backdrop-blur-sm p-4 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.04)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.08)] transition-all group cursor-pointer hover:scale-[1.01]`}
            >
                <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-2">
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${cfg.color}`}>
                            <IconComp size={14} />
                        </div>
                        <span className="text-[11px] font-semibold text-neutral-muted">{cfg.label}</span>
                    </div>
                    <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        isPending
                            ? 'bg-surface-sub text-neutral-muted dark:bg-surface-hover/40'
                            : isApproved
                                ? 'bg-success-bg text-success dark:bg-success-bg'
                                : 'bg-error-bg text-error dark:bg-error-bg'
                    }`}>
                        {isPending ? <Clock size={10} /> : isApproved ? <CheckCircle2 size={10} /> : <XCircle size={10} />}
                        {isPending ? '대기중' : isApproved ? 'Approved' : 'Rejected'}
                    </span>
                </div>
                <h4 className="text-[13px] font-bold text-neutral-main leading-snug mb-1 line-clamp-2">{item.title}</h4>
                {item.detail && (
                    <p className="text-[11px] text-neutral-muted line-clamp-1 mb-2">{item.detail}</p>
                )}
                {/* 첨부파일 표시 */}
                {item.file_name && (
                    <div className="flex items-center gap-1 mb-2">
                        <Paperclip size={10} className="text-neutral-muted" />
                        <span className="text-[10px] text-neutral-muted truncate">{item.file_name}</span>
                    </div>
                )}
                {/* 받는 사람 표시 */}
                <div className="flex items-center gap-2 pt-2.5 border-t border-neutral-divider dark:border-neutral-border">
                    <Send size={10} className="text-neutral-muted shrink-0" />
                    {item.target_user_avatar ? (
                        <img src={item.target_user_avatar} alt="" className="w-7 h-7 rounded-full object-cover ring-2 ring-white dark:ring-neutral-800" />
                    ) : (
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold ${isPending ? 'bg-surface-sub dark:bg-surface-hover/30 text-neutral-sub' : isApproved ? 'bg-success-bg dark:bg-success-bg text-success' : 'bg-error-bg dark:bg-error-bg text-error'}`}>
                            {(item.target_user_name || item.target_team || '?')[0]}
                        </div>
                    )}
                    <span className="text-[11px] font-medium text-neutral-sub truncate">
                        {item.target_user_name || item.target_team || '알 수 없음'}
                        {(item.target_user_team || item.target_team) && <span className="text-[9px] text-neutral-muted ml-1">({item.target_user_team || item.target_team})</span>}
                    </span>
                    {item.created_at && (
                        <span className="text-[10px] text-neutral-muted ml-auto shrink-0">
                            {timeAgo(item.created_at)}
                        </span>
                    )}
                </div>
            </motion.div>
        );
    };

    const pendingItems = items.filter(i => i.status === 'pending' && (!user || String(i.requester_id) !== String(user.id)));
    const sentItems = items.filter(i => user && String(i.requester_id) === String(user.id));

    // 이미 보낸 요청과 같은 type+title인 추천은 제외
    const filteredSuggestions = suggestions.filter(s =>
        !sentItems.some(sent => sent.type === s.type && sent.title === s.title)
    );

    /* ── New Tasks 탭 전환 시 데이터 로드 ── */
    const switchNewTasksTab = (tab) => {
        setNewTasksTab(tab);
        if (tab === 'schedules' && scheduleSuggestions.length === 0 && !schedSuggestLoading) {
            loadScheduleSuggestions();
        }
    };

    return (
        <div className="space-y-4">
            {loading ? (
                <div className="flex items-center justify-center h-64 text-neutral-muted">
                    <RefreshCw className="animate-spin mr-2" size={18} /> 로딩 중...
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                    {/* ── Pending column ── */}
                    <div className="flex flex-col min-h-[420px]">
                        <div className="flex items-center justify-center gap-2 mb-3">
                            <div className="w-2 h-2 rounded-full bg-info" />
                            <span className="text-sm font-bold text-neutral-main tracking-tight">Pending</span>
                            <span className="text-[11px] font-semibold text-neutral-muted bg-surface-sub dark:bg-surface-hover px-2 py-0.5 rounded-full">
                                {pendingItems.length}
                            </span>
                        </div>
                        <div className="flex-1 bg-surface-hover/80 dark:bg-surface-card/40 rounded-2xl p-4 border border-neutral-border/50 dark:border-neutral-border/50">
                            <div className="space-y-3">
                                <AnimatePresence mode="popLayout">
                                    {pendingItems.map(renderPendingCard)}
                                </AnimatePresence>
                                {pendingItems.length === 0 && (
                                    <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-neutral-border dark:border-neutral-border">
                                        <span className="text-[11px] text-neutral-muted dark:text-neutral-muted">비어 있음</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* ── Sent column (Approved + Rejected 통합) ── */}
                    <div className="flex flex-col min-h-[420px]">
                        <div className="flex items-center justify-center gap-2 mb-3">
                            <div className="w-2 h-2 rounded-full bg-warning" />
                            <span className="text-sm font-bold text-neutral-main tracking-tight">Sent</span>
                            <span className="text-[11px] font-semibold text-neutral-muted bg-surface-sub dark:bg-surface-hover px-2 py-0.5 rounded-full">
                                {sentItems.length}
                            </span>
                        </div>
                        <div className="flex-1 bg-surface-hover/80 dark:bg-surface-card/40 rounded-2xl p-4 border border-neutral-border/50 dark:border-neutral-border/50">
                            <div className="space-y-3">
                                <AnimatePresence mode="popLayout">
                                    {sentItems.map(renderSentCard)}
                                </AnimatePresence>
                                {sentItems.length === 0 && (
                                    <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-neutral-border dark:border-neutral-border">
                                        <span className="text-[11px] text-neutral-muted dark:text-neutral-muted">비어 있음</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* ── Column 3: New Tasks (AI 추천 - 결재 + 일정) ── */}
                    <div className="flex flex-col min-h-[420px]">
                        <div className="flex items-center justify-center gap-2 mb-3">
                            <div className="w-2 h-2 rounded-full bg-primary-500" />
                            <span className="text-sm font-bold text-neutral-main tracking-tight">New Tasks</span>
                            <button
                                onClick={() => newTasksTab === 'approvals' ? handleSuggest() : loadScheduleSuggestions()}
                                disabled={suggestLoading || schedSuggestLoading}
                                className="p-1 rounded-lg hover:bg-neutral-divider/60 dark:hover:bg-surface-hover/40 text-neutral-muted hover:text-neutral-sub transition-colors"
                                title="새로고침"
                            >
                                <RefreshCw size={12} className={(suggestLoading || schedSuggestLoading) ? 'animate-spin' : ''} />
                            </button>
                        </div>

                        {/* Model info badge */}
                        {(() => {
                            const info = newTasksTab === 'approvals' ? suggestModelInfo : schedModelInfo;
                            if (!info) return null;
                            const isSllm = info.provider === 'sllm';
                            const isFallback = info.provider === 'fallback';
                            const badgeColor = isSllm
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : isFallback
                                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                                    : 'bg-blue-50 text-blue-700 border-blue-200';
                            const displayName = isSllm ? 'Kanana-1.5-8B' : isFallback ? 'GPT-4o-mini' : info.model;
                            return (
                                <div className="flex items-center justify-center gap-1.5 mb-1">
                                    <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full border ${badgeColor}`}>
                                        {displayName}
                                    </span>
                                </div>
                            );
                        })()}

                        {/* Sub-tabs */}
                        <div className="flex gap-1 mb-2">
                            <button
                                onClick={() => switchNewTasksTab('approvals')}
                                className={`flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all ${newTasksTab === 'approvals' ? 'bg-primary-100 text-primary-700' : 'text-neutral-muted hover:bg-surface-sub'}`}
                            >
                                결재 추천
                            </button>
                            <button
                                onClick={() => switchNewTasksTab('schedules')}
                                className={`flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all flex items-center justify-center gap-1 ${newTasksTab === 'schedules' ? 'bg-primary-100 text-primary-700' : 'text-neutral-muted hover:bg-surface-sub'}`}
                            >
                                <CalendarClock size={11} /> 일정 추천
                            </button>
                        </div>

                        <div className="flex-1 bg-surface-hover/80 dark:bg-surface-card/40 rounded-2xl p-4 border border-neutral-border/50 dark:border-neutral-border/50 overflow-y-auto max-h-[560px]">
                            {/* ── 결재 추천 탭 ── */}
                            {newTasksTab === 'approvals' && (
                                <>
                                    {suggestContext && !suggestLoading && (
                                        <div className="flex flex-wrap gap-1.5 mb-3">
                                            <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-info-bg text-info">태스크 {suggestContext.total_tasks}</span>
                                            <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-success-bg text-success">완료 {suggestContext.done_pct}%</span>
                                            <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-primary-50 text-primary-700">일정 {suggestContext.upcoming_events}</span>
                                        </div>
                                    )}
                                    {suggestLoading ? (
                                        <div className="flex flex-col items-center justify-center py-12">
                                            <div className="relative w-10 h-10 mb-3">
                                                <div className="absolute inset-0 rounded-full border-2 border-primary-100" />
                                                <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-primary-500 animate-spin" />
                                                <Sparkles size={14} className="absolute inset-0 m-auto text-primary-500" />
                                            </div>
                                            <p className="text-xs text-neutral-muted">분석 중...</p>
                                        </div>
                                    ) : suggestError ? (
                                        <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-error-bg dark:border-error-bg bg-error-bg/50 dark:bg-error-bg/10">
                                            <XCircle size={14} className="text-error mb-1" />
                                            <span className="text-[10px] text-error text-center px-2 leading-relaxed">{suggestError}</span>
                                            <button onClick={handleSuggest} className="mt-1.5 text-[10px] text-primary-700 hover:underline">다시 시도</button>
                                        </div>
                                    ) : filteredSuggestions.length === 0 ? (
                                        <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-neutral-border dark:border-neutral-border">
                                            <Zap size={14} className="text-neutral-muted mb-1" />
                                            <span className="text-[11px] text-neutral-muted">추천 없음</span>
                                        </div>
                                    ) : (
                                        <div className="grid grid-cols-2 gap-2.5">
                                            <AnimatePresence mode="popLayout">
                                                {filteredSuggestions.map((s, idx) => {
                                                    const cfg = typeConfig[s.type] || defaultTypeConfig;
                                                    // 백엔드에서 related_project가 없으면 파이프라인 태스크에서 추론
                                                    const project = s.related_project || (() => {
                                                        const match = pipelineTasks.find(t => t.stage !== 'done' && t.project && s.title?.includes(t.title));
                                                        if (match) return match.project;
                                                        // review 타입이면 review 단계 태스크의 프로젝트
                                                        if (s.type === 'review') {
                                                            const rt = pipelineTasks.find(t => t.stage === 'review' && t.project);
                                                            if (rt) return rt.project;
                                                        }
                                                        // 가장 많은 프로젝트
                                                        const projCounts = {};
                                                        pipelineTasks.filter(t => t.project && t.stage !== 'done').forEach(t => { projCounts[t.project] = (projCounts[t.project] || 0) + 1; });
                                                        const entries = Object.entries(projCounts);
                                                        return entries.length > 0 ? entries.sort((a, b) => b[1] - a[1])[0][0] : null;
                                                    })();
                                                    return (
                                                        <motion.div
                                                            key={idx}
                                                            layout
                                                            initial={{ opacity: 0, y: 6 }}
                                                            animate={{ opacity: 1, y: 0 }}
                                                            transition={{ delay: idx * 0.05 }}
                                                            onClick={() => applySuggestion(s, idx)}
                                                            className="bg-white dark:bg-neutral-800 p-3 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] cursor-pointer transition-all group"
                                                        >
                                                            <div className="flex flex-col items-center text-center gap-1.5">
                                                                <div className="flex items-center justify-between w-full">
                                                                    {project && (
                                                                        <span className="text-[8px] font-semibold px-1.5 py-0.5 rounded-md bg-primary-50 text-primary-700 dark:bg-primary-50 flex items-center gap-0.5">
                                                                            <FolderOpen size={8} /> {project}
                                                                        </span>
                                                                    )}
                                                                    {!project && <span />}
                                                                    {s.priority && (
                                                                        <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-md ${priorityBadge[s.priority] || priorityBadge.medium}`}>
                                                                            {s.priority.toUpperCase()}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                                <h4 className="text-[11px] font-bold text-neutral-main group-hover:text-primary-700 transition-colors line-clamp-2 leading-snug">
                                                                    {s.title}
                                                                </h4>
                                                                {s.reason && (
                                                                    <p className="text-[9px] text-neutral-muted line-clamp-2 leading-relaxed">{s.reason}</p>
                                                                )}
                                                                {s.regulation_warning && (
                                                                    <div className={`w-full flex items-start gap-1.5 p-2 rounded-lg mt-1 ${
                                                                        s.regulation_warning.level === 'danger'
                                                                            ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
                                                                            : 'bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800'
                                                                    }`}>
                                                                        <ShieldCheck size={11} className={s.regulation_warning.level === 'danger' ? 'text-red-500 shrink-0 mt-0.5' : 'text-amber-500 shrink-0 mt-0.5'} />
                                                                        <div className="text-left">
                                                                            <p className={`text-[9px] font-bold ${s.regulation_warning.level === 'danger' ? 'text-red-600 dark:text-red-400' : 'text-amber-600 dark:text-amber-400'}`}>
                                                                                {s.regulation_warning.level === 'danger' ? '규정 위반' : '규정 확인 필요'}
                                                                            </p>
                                                                            <p className="text-[8px] text-neutral-sub leading-relaxed">{s.regulation_warning.message}</p>
                                                                            {s.regulation_warning.regulation && s.regulation_warning.regulation !== 'no_regulation' && (
                                                                                <p className="text-[8px] text-neutral-muted mt-0.5">근거: {s.regulation_warning.regulation}</p>
                                                                            )}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                                <Plus size={12} className="text-neutral-muted group-hover:text-primary-500 transition-colors mt-0.5" />
                                                            </div>
                                                        </motion.div>
                                                    );
                                                })}
                                            </AnimatePresence>
                                        </div>
                                    )}
                                </>
                            )}

                            {/* ── 일정 추천 탭 ── */}
                            {newTasksTab === 'schedules' && (
                                <>
                                    {schedSuggestLoading ? (
                                        <div className="flex flex-col items-center justify-center py-12">
                                            <div className="relative w-10 h-10 mb-3">
                                                <div className="absolute inset-0 rounded-full border-2 border-primary-100" />
                                                <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-primary-500 animate-spin" />
                                                <CalendarClock size={14} className="absolute inset-0 m-auto text-primary-500" />
                                            </div>
                                            <p className="text-xs text-neutral-muted">일정 분석 중...</p>
                                        </div>
                                    ) : schedSuggestError ? (
                                        <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-error-bg dark:border-error-bg bg-error-bg/50 dark:bg-error-bg/10">
                                            <XCircle size={14} className="text-error mb-1" />
                                            <span className="text-[10px] text-error text-center px-2 leading-relaxed">{schedSuggestError}</span>
                                            <button onClick={loadScheduleSuggestions} className="mt-1.5 text-[10px] text-primary-700 hover:underline">다시 시도</button>
                                        </div>
                                    ) : scheduleSuggestions.length === 0 ? (
                                        <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-neutral-border dark:border-neutral-border">
                                            <CalendarClock size={14} className="text-neutral-muted mb-1" />
                                            <span className="text-[11px] text-neutral-muted">추천 일정 없음</span>
                                        </div>
                                    ) : (
                                        <div className="space-y-2.5">
                                            <AnimatePresence mode="popLayout">
                                                {scheduleSuggestions.map((s, idx) => {
                                                    const stCfg = scheduleTypeConfig[s.schedule_type] || scheduleTypeConfig.task;
                                                    const isAdding = addingScheduleId === idx;
                                                    return (
                                                        <motion.div
                                                            key={idx}
                                                            layout
                                                            initial={{ opacity: 0, y: 6 }}
                                                            animate={{ opacity: 1, y: 0 }}
                                                            exit={{ opacity: 0, x: 20, scale: 0.95 }}
                                                            transition={{ delay: idx * 0.05 }}
                                                            className="bg-white dark:bg-neutral-800 p-3.5 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] transition-all"
                                                        >
                                                            <div className="flex items-start justify-between gap-2 mb-2">
                                                                <div className="flex items-center gap-1.5">
                                                                    <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-md ${stCfg.color}`}>
                                                                        {stCfg.label}
                                                                    </span>
                                                                    {s.priority && (
                                                                        <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-md ${priorityBadge[s.priority] || priorityBadge.medium}`}>
                                                                            {s.priority.toUpperCase()}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                                {s.duration_minutes && (
                                                                    <span className="text-[9px] text-neutral-muted shrink-0">{s.duration_minutes}분</span>
                                                                )}
                                                            </div>
                                                            <h4 className="text-[12px] font-bold text-neutral-main leading-snug mb-1 line-clamp-2">
                                                                {s.title}
                                                            </h4>
                                                            {s.reason && (
                                                                <p className="text-[9px] text-neutral-muted line-clamp-2 leading-relaxed mb-2">{s.reason}</p>
                                                            )}
                                                            {s.suggested_day && (
                                                                <span className="text-[9px] text-neutral-muted block mb-2">
                                                                    {s.suggested_day === 'today' ? '오늘' : s.suggested_day === 'tomorrow' ? '내일' : s.suggested_day === 'this_week' ? '이번 주' : s.suggested_day}
                                                                </span>
                                                            )}
                                                            {s.regulation_warning && (
                                                                <div className={`flex items-start gap-1.5 p-2 rounded-lg mb-2 ${
                                                                    s.regulation_warning.level === 'danger'
                                                                        ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
                                                                        : 'bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800'
                                                                }`}>
                                                                    <ShieldCheck size={12} className={s.regulation_warning.level === 'danger' ? 'text-red-500 shrink-0 mt-0.5' : 'text-amber-500 shrink-0 mt-0.5'} />
                                                                    <div>
                                                                        <p className={`text-[9px] font-bold ${s.regulation_warning.level === 'danger' ? 'text-red-600 dark:text-red-400' : 'text-amber-600 dark:text-amber-400'}`}>
                                                                            {s.regulation_warning.level === 'danger' ? '규정 위반' : '규정 확인 필요'}
                                                                        </p>
                                                                        <p className="text-[8px] text-neutral-sub leading-relaxed">{s.regulation_warning.message}</p>
                                                                        {s.regulation_warning.regulation && s.regulation_warning.regulation !== 'no_regulation' && (
                                                                            <p className="text-[8px] text-neutral-muted mt-0.5">근거: {s.regulation_warning.regulation}</p>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            )}
                                                            <button
                                                                onClick={() => openSchedulePicker(s, idx)}
                                                                disabled={isAdding}
                                                                className="w-full flex items-center justify-center gap-1.5 py-2 bg-primary-50 hover:bg-primary-700 text-primary-700 hover:text-white text-[11px] font-bold rounded-lg transition-all disabled:opacity-50"
                                                            >
                                                                {isAdding ? (
                                                                    <RefreshCw size={12} className="animate-spin" />
                                                                ) : (
                                                                    <CalendarPlus size={12} />
                                                                )}
                                                                {isAdding ? '추가 중...' : '캘린더에 추가'}
                                                            </button>
                                                        </motion.div>
                                                    );
                                                })}
                                            </AnimatePresence>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* 삭제 확인 모달 */}
            {deleteConfirm && createPortal(
                <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/40 p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="absolute inset-0"
                        onClick={() => setDeleteConfirm(null)}
                    />
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-3xl shadow-2xl p-6 w-full max-w-sm border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex flex-col items-center text-center">
                            <div className="w-12 h-12 rounded-full bg-error-bg flex items-center justify-center mb-3">
                                <Trash2 size={20} className="text-error" />
                            </div>
                            <h3 className="text-base font-bold text-neutral-main dark:text-white mb-1">요청을 삭제하시겠습니까?</h3>
                            <p className="text-sm text-neutral-muted mb-5 line-clamp-2">"{deleteConfirm.title}"</p>
                            <div className="flex gap-3 w-full">
                                <button
                                    onClick={() => setDeleteConfirm(null)}
                                    className="flex-1 py-2.5 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
                                >
                                    취소
                                </button>
                                <button
                                    onClick={handleDeleteConfirm}
                                    className="flex-1 py-2.5 bg-error text-white text-xs font-black rounded-xl shadow-xl shadow-error/20 hover:bg-error/90 hover:scale-105 transition-all"
                                >
                                    삭제
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </div>,
                document.body
            )}

            {/* 새 요청 모달 */}
            {showModal && createPortal(
                <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/40 p-4">
                    <AnimatePresence>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0"
                            onClick={() => { setShowModal(false); setAppliedSuggestionIdx(null); }}
                        />
                    </AnimatePresence>
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 w-full max-w-md mx-4 overflow-hidden border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-lg font-bold text-neutral-main dark:text-white">새 요청 올리기</h3>
                            <button onClick={() => { setShowModal(false); setAppliedSuggestionIdx(null); }} className="w-8 h-8 rounded-lg hover:bg-surface-sub dark:hover:bg-white/5 text-neutral-muted transition-colors flex items-center justify-center">
                                <X size={18} />
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">유형</label>
                                <select
                                    value={formData.type}
                                    onChange={(e) => setFormData(prev => ({ ...prev, type: e.target.value }))}
                                    className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-border dark:border-neutral-border bg-white dark:bg-surface-card text-sm outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                >
                                    {Object.entries(typeConfig).map(([key, cfg]) => (
                                        <option key={key} value={key}>{cfg.label}</option>
                                    ))}
                                </select>
                            </div>
                            {formData.type === 'other' && (
                                <div>
                                    <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">유형 직접 입력</label>
                                    <input
                                        type="text"
                                        value={formData.customType}
                                        onChange={(e) => setFormData(prev => ({ ...prev, customType: e.target.value }))}
                                        placeholder="예: 출장 신청, 장비 요청 등"
                                        className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-border dark:border-neutral-border bg-white dark:bg-surface-card text-sm outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                    />
                                </div>
                            )}
                            {/* 대상 팀 / 팀원 선택 */}
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">보낼 팀</label>
                                    <select
                                        value={formData.target_team}
                                        onChange={(e) => setFormData(prev => ({ ...prev, target_team: e.target.value, target_user_id: '' }))}
                                        className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-border dark:border-neutral-border bg-white dark:bg-surface-card text-sm outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                    >
                                        <option value="">전체</option>
                                        {TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">보낼 팀원</label>
                                    <MemberDropdown
                                        members={allMembers.filter(m => !formData.target_team || m.team === formData.target_team)}
                                        value={formData.target_user_id}
                                        onChange={(id) => setFormData(prev => ({ ...prev, target_user_id: id }))}
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">제목</label>
                                <input
                                    type="text"
                                    value={formData.title}
                                    onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                                    placeholder="요청 제목을 입력하세요"
                                    className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-border dark:border-neutral-border bg-white dark:bg-surface-card text-sm outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all placeholder:text-neutral-muted"
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">상세 내용</label>
                                <textarea
                                    value={formData.detail}
                                    onChange={(e) => setFormData(prev => ({ ...prev, detail: e.target.value }))}
                                    placeholder="상세 내용을 입력하세요 (선택)"
                                    rows={4}
                                    className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-border dark:border-neutral-border bg-white dark:bg-surface-card text-sm outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none transition-all placeholder:text-neutral-muted"
                                />
                            </div>
                            <div>
                                <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">첨부파일 (선택)</label>
                                <input
                                    type="file"
                                    accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg,.gif,.webp"
                                    onChange={(e) => setFormFile(e.target.files[0] || null)}
                                    className="w-full text-sm text-neutral-muted file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-surface-sub file:text-neutral-sub hover:file:bg-neutral-divider dark:file:bg-surface-hover dark:file:text-neutral-sub"
                                />
                                {formFile && (
                                    <div className="flex items-center gap-1 mt-1 text-xs text-neutral-muted">
                                        <Paperclip size={12} />
                                        <span className="truncate">{formFile.name}</span>
                                        <button type="button" onClick={() => setFormFile(null)} className="ml-1 p-0.5 rounded hover:bg-error-bg text-error hover:text-error transition-colors">
                                            <X size={14} />
                                        </button>
                                    </div>
                                )}
                            </div>
                            <div className="flex gap-3 pt-3">
                                <button
                                    type="button"
                                    onClick={() => { setShowModal(false); setAppliedSuggestionIdx(null); }}
                                    className="flex-1 py-2.5 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
                                >
                                    취소
                                </button>
                                <button
                                    type="submit"
                                    disabled={submitting || !formData.target_user_id}
                                    className="flex-1 py-2.5 bg-primary-700 text-white text-xs font-black rounded-xl shadow-xl shadow-primary-700/20 hover:bg-primary-800 hover:scale-105 transition-all disabled:opacity-50"
                                >
                                    {submitting ? '제출 중...' : !formData.target_user_id ? '팀원 선택 필요' : '요청 제출'}
                                </button>
                            </div>
                        </form>
                    </motion.div>
                </div>,
                document.body
            )}

            {/* ── Sent 상세 모달 ── */}
            {selectedSent && createPortal(
                <div className="fixed inset-0 z-[130] flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
                        onClick={closeSentDetail}
                    />
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        className="relative backdrop-blur-xl rounded-3xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden bg-white/80 dark:bg-neutral-900/80"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* 헤더 */}
                        <div className="px-6 pt-6 pb-4">
                            <div className="flex items-start justify-between">
                                <div className="flex items-center gap-3">
                                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${(typeConfig[selectedSent.type] || defaultTypeConfig).color}`}>
                                        {(() => { const IC = (typeConfig[selectedSent.type] || defaultTypeConfig).icon; return <IC size={20} />; })()}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <span className="text-[11px] font-semibold text-neutral-muted">{(typeConfig[selectedSent.type] || defaultTypeConfig).label}</span>
                                        {editMode ? (
                                            <input
                                                value={editTitle}
                                                onChange={(e) => setEditTitle(e.target.value)}
                                                className="w-full text-lg font-bold text-neutral-main dark:text-white bg-white/60 dark:bg-black/20 border border-neutral-border dark:border-neutral-border rounded-lg px-2 py-1 outline-none focus:ring-2 focus:ring-primary-500"
                                            />
                                        ) : (
                                            <h3 className="text-lg font-bold text-neutral-main dark:text-white leading-tight">{selectedSent.title}</h3>
                                        )}
                                    </div>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                    <span className={`inline-flex items-center gap-1 text-xs font-bold px-3 py-1 rounded-full ${selectedSent.status === 'approved'
                                        ? 'bg-success-bg text-success dark:bg-success-bg dark:text-success'
                                        : selectedSent.status === 'pending'
                                            ? 'bg-warning-bg text-warning dark:bg-warning-bg dark:text-warning'
                                            : 'bg-error-bg text-error dark:bg-error-bg dark:text-error'
                                    }`}>
                                        {selectedSent.status === 'approved' ? <CheckCircle2 size={14} /> : selectedSent.status === 'pending' ? <Clock size={14} /> : <XCircle size={14} />}
                                        {selectedSent.status === 'approved' ? 'Approved' : selectedSent.status === 'pending' ? '대기중' : 'Rejected'}
                                    </span>
                                    <button onClick={closeSentDetail} className="w-8 h-8 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 text-neutral-muted transition-colors flex items-center justify-center">
                                        <X size={18} />
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div className="px-6 pb-6 space-y-4 max-h-[60vh] overflow-y-auto">
                            {/* 상세 내용 */}
                            <div className="mt-4">
                                <h4 className="text-[11px] font-bold text-neutral-muted uppercase tracking-wider mb-2">상세 내용</h4>
                                {editMode ? (
                                    <textarea
                                        value={editDetail}
                                        onChange={(e) => setEditDetail(e.target.value)}
                                        rows={4}
                                        className="w-full text-sm text-neutral-main dark:text-neutral-sub bg-white/60 dark:bg-black/20 border border-neutral-border dark:border-neutral-border rounded-xl px-3 py-2.5 outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                                        placeholder="상세 내용을 입력하세요"
                                    />
                                ) : (
                                    <p className="text-sm text-neutral-main dark:text-neutral-sub whitespace-pre-wrap bg-surface-hover dark:bg-surface-card/50 p-3 rounded-xl">
                                        {selectedSent.detail || '(내용 없음)'}
                                    </p>
                                )}
                            </div>

                            {/* 받는 사람 */}
                            <div className="bg-surface-hover dark:bg-surface-card/50 p-4 rounded-xl">
                                <span className="text-[10px] font-bold text-neutral-muted uppercase tracking-wider">받는 사람</span>
                                <div className="flex items-center gap-3 mt-2">
                                    {selectedSent.target_user_avatar ? (
                                        <img src={selectedSent.target_user_avatar} alt="" className="w-9 h-9 rounded-full object-cover ring-2 ring-white dark:ring-neutral-800" />
                                    ) : (
                                        <div className="w-9 h-9 rounded-full bg-primary-100 dark:bg-primary-50 flex items-center justify-center text-sm font-bold text-primary-700">
                                            {(selectedSent.target_user_name || selectedSent.target_team || '?')[0]}
                                        </div>
                                    )}
                                    <span className="text-sm font-semibold text-neutral-main dark:text-neutral-sub">
                                        {selectedSent.target_user_name || selectedSent.target_team || '알 수 없음'}
                                        {(selectedSent.target_user_team || selectedSent.target_team) && <span className="text-xs text-neutral-muted font-normal ml-1">({selectedSent.target_user_team || selectedSent.target_team})</span>}
                                    </span>
                                </div>
                            </div>

                            {/* 시간 정보 */}
                            <div className="flex items-center gap-4 text-[11px] text-neutral-muted">
                                <div className="flex items-center gap-1.5">
                                    <Clock size={12} />
                                    <span>요청일: {selectedSent.created_at ? new Date(selectedSent.created_at).toLocaleString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-'}</span>
                                </div>
                                <span className="text-neutral-muted">•</span>
                                <span>{timeAgo(selectedSent.created_at)}</span>
                            </div>

                            {/* 첨부파일 */}
                            {selectedSent.file_name && (
                                <div>
                                    <h4 className="text-[11px] font-bold text-neutral-muted uppercase tracking-wider mb-2">첨부파일</h4>
                                    <div className="border border-neutral-border dark:border-neutral-border rounded-xl overflow-hidden">
                                        {/* 미리보기 (이미지/PDF) */}
                                        {previewUrl && /\.(png|jpg|jpeg|gif|webp)$/i.test(selectedSent.file_name) && (
                                            <div className="bg-surface-hover dark:bg-surface-card p-2">
                                                <img src={previewUrl} alt={selectedSent.file_name} className="max-h-64 mx-auto rounded-lg object-contain" />
                                            </div>
                                        )}
                                        {previewUrl && /\.pdf$/i.test(selectedSent.file_name) && (
                                            <div className="bg-surface-hover dark:bg-surface-card">
                                                <iframe src={previewUrl} className="w-full h-64" title="PDF Preview" />
                                            </div>
                                        )}
                                        <div className="flex items-center justify-between p-3 bg-white dark:bg-neutral-800">
                                            <div className="flex items-center gap-2 min-w-0">
                                                <Paperclip size={14} className="text-neutral-muted shrink-0" />
                                                <span className="text-sm text-neutral-main dark:text-neutral-sub truncate">{selectedSent.file_name}</span>
                                            </div>
                                            <div className="flex gap-1.5 shrink-0">
                                                {previewUrl && (
                                                    <a
                                                        href={previewUrl}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="p-1.5 rounded-lg bg-surface-sub hover:bg-neutral-divider dark:bg-surface-hover dark:hover:bg-neutral-border text-neutral-sub transition-colors"
                                                        title="미리보기"
                                                    >
                                                        <Eye size={14} />
                                                    </a>
                                                )}
                                                <button
                                                    onClick={() => downloadApprovalFile(selectedSent.id, selectedSent.file_name)}
                                                    className="p-1.5 rounded-lg bg-primary-50 hover:bg-primary-100 dark:bg-primary-50/20 dark:hover:bg-primary-50/40 text-primary-700 transition-colors"
                                                    title="다운로드"
                                                >
                                                    <Download size={14} />
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* 액션 버튼 */}
                            <div className="pt-2 border-t border-neutral-divider dark:border-neutral-border flex gap-2">
                                {editMode ? (
                                    <>
                                        <button
                                            onClick={() => setEditMode(false)}
                                            className="flex-1 py-2.5 text-xs font-semibold text-neutral-muted hover:text-neutral-sub hover:bg-surface-hover dark:hover:bg-surface-card rounded-xl transition-all"
                                        >
                                            취소
                                        </button>
                                        <button
                                            onClick={saveEdit}
                                            disabled={editSaving || !editTitle.trim()}
                                            className="flex-1 py-2.5 text-xs font-semibold text-white bg-primary-700 hover:bg-primary-900 rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-1.5"
                                        >
                                            <Check size={13} /> {editSaving ? '저장 중...' : '저장'}
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <button
                                            onClick={startEdit}
                                            className="flex-1 py-2.5 text-xs font-semibold text-primary-700 hover:text-primary-900 hover:bg-primary-50 dark:hover:bg-primary-50/20 rounded-xl transition-all flex items-center justify-center gap-1.5"
                                        >
                                            <Pencil size={13} /> 수정
                                        </button>
                                        <button
                                            onClick={() => { closeSentDetail(); handleDeleteClick(selectedSent); }}
                                            className="flex-1 py-2.5 text-xs font-semibold text-error hover:text-error hover:bg-error-bg dark:hover:bg-error-bg/20 rounded-xl transition-all flex items-center justify-center gap-1.5"
                                        >
                                            <Trash2 size={13} /> 삭제
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>
                    </motion.div>
                </div>,
                document.body
            )}

            {/* ── 일정 날짜 선택 모달 ── */}
            {schedulePickerData && createPortal(
                <div className="fixed inset-0 z-[140] flex items-center justify-center bg-black/40 p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="absolute inset-0"
                        onClick={() => setSchedulePickerData(null)}
                    />
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-3xl shadow-2xl p-6 w-full max-w-sm border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-5">
                            <div className="flex items-center gap-2">
                                <div className="w-10 h-10 rounded-xl bg-primary-50 dark:bg-primary-50 flex items-center justify-center">
                                    <CalendarPlus size={20} className="text-primary-700" />
                                </div>
                                <h3 className="text-base font-bold text-neutral-main dark:text-white">일정 추가</h3>
                            </div>
                            <button onClick={() => setSchedulePickerData(null)} className="w-8 h-8 rounded-lg hover:bg-surface-sub dark:hover:bg-white/5 text-neutral-muted transition-colors flex items-center justify-center">
                                <X size={18} />
                            </button>
                        </div>

                        {/* 일정 제목 (수정 가능) */}
                        <div className="space-y-3">
                            <div>
                                <input
                                    type="text"
                                    value={pickerTitle}
                                    onChange={(e) => setPickerTitle(e.target.value)}
                                    placeholder="일정 이름을 입력하세요"
                                    className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-border dark:border-neutral-border bg-white dark:bg-surface-card text-sm font-semibold outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all placeholder:text-neutral-muted"
                                />
                                {schedulePickerData.suggestion.reason && (
                                    <p className="text-[10px] text-neutral-muted mt-1.5 ml-0.5 line-clamp-2">{schedulePickerData.suggestion.reason}</p>
                                )}
                            </div>

                            {/* 일정 유형 토글 */}
                            <div>
                                <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">일정 유형</label>
                                <div className="flex gap-1.5 flex-wrap">
                                    {[
                                        { value: 'meeting', label: '회의', color: 'bg-blue-100 text-blue-700 border-blue-300' },
                                        { value: 'deadline', label: '마감일', color: 'bg-red-100 text-red-700 border-red-300' },
                                        { value: 'project', label: '프로젝트', color: 'bg-green-100 text-green-700 border-green-300' },
                                        { value: 'personal', label: '개인 일정', color: 'bg-gray-100 text-gray-700 border-gray-300' },
                                    ].map(t => (
                                        <button
                                            key={t.value}
                                            onClick={() => setPickerScheduleType(t.value)}
                                            className={`px-3 py-1.5 rounded-full text-[11px] font-bold border transition-all ${
                                                pickerScheduleType === t.value
                                                    ? t.color + ' ring-2 ring-offset-1 ring-primary-300'
                                                    : 'bg-white dark:bg-surface-card text-neutral-muted border-neutral-border hover:border-neutral-400'
                                            }`}
                                        >
                                            {t.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* 공유 범위 */}
                            <div>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setPickerShareScope('team')}
                                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold border transition-all ${
                                            pickerShareScope === 'team'
                                                ? 'bg-primary-50 text-primary-700 border-primary-300'
                                                : 'bg-white dark:bg-surface-card text-neutral-muted border-neutral-border'
                                        }`}
                                    >
                                        팀 공유
                                    </button>
                                    <button
                                        onClick={() => setPickerShareScope('project')}
                                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold border transition-all ${
                                            pickerShareScope === 'project'
                                                ? 'bg-purple-50 text-purple-700 border-purple-300'
                                                : 'bg-white dark:bg-surface-card text-neutral-muted border-neutral-border'
                                        }`}
                                    >
                                        프로젝트 공유
                                    </button>
                                </div>
                            </div>

                            {/* 날짜 */}
                            <div>
                                <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">날짜</label>
                                <DatePicker
                                    value={pickerDate}
                                    onChange={(date) => setPickerDate(date)}
                                    placeholder="날짜를 선택하세요"
                                />
                            </div>

                            {/* Google Meet + 종일 */}
                            <div className="flex items-center gap-4">
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={pickerGoogleMeet}
                                        onChange={(e) => setPickerGoogleMeet(e.target.checked)}
                                        className="w-4 h-4 rounded border-neutral-border accent-primary-700"
                                    />
                                    <span className="text-sm text-neutral-main dark:text-neutral-sub">
                                        Google Meet 링크 생성
                                    </span>
                                </label>
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={pickerAllDay}
                                        onChange={(e) => setPickerAllDay(e.target.checked)}
                                        className="w-4 h-4 rounded border-neutral-border accent-primary-700"
                                    />
                                    <span className="text-sm text-neutral-main dark:text-neutral-sub">종일</span>
                                </label>
                            </div>

                            {/* 참석자 이메일 (Google Meet 체크 시 표시) */}
                            {pickerGoogleMeet && (
                                <div>
                                    <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">참석자 초대 (이메일)</label>
                                    <textarea
                                        value={pickerAttendees}
                                        onChange={(e) => setPickerAttendees(e.target.value)}
                                        placeholder="이메일을 쉼표(,)로 구분하여 입력&#10;예: kim@company.com, lee@company.com"
                                        rows={2}
                                        className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-border dark:border-neutral-border bg-white dark:bg-surface-card text-sm outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all placeholder:text-neutral-muted resize-none"
                                    />
                                    {pickerAttendees && (
                                        <p className="text-[10px] text-neutral-muted mt-1 ml-0.5">
                                            {pickerAttendees.split(',').filter(e => e.trim().includes('@')).length}명 초대 예정 — Meet 링크 + 초대 메일이 발송됩니다
                                        </p>
                                    )}
                                </div>
                            )}

                            {/* 시간 선택 */}
                            {!pickerAllDay && (
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">시작 시간</label>
                                        <input
                                            type="time"
                                            value={pickerStartTime}
                                            onChange={(e) => setPickerStartTime(e.target.value)}
                                            className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-border dark:border-neutral-border bg-white dark:bg-surface-card text-sm outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-[11px] font-semibold text-neutral-muted mb-1.5 ml-0.5">종료 시간</label>
                                        <input
                                            type="time"
                                            value={pickerEndTime}
                                            onChange={(e) => setPickerEndTime(e.target.value)}
                                            className="w-full px-3.5 py-2.5 rounded-lg border border-neutral-border dark:border-neutral-border bg-white dark:bg-surface-card text-sm outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
                                        />
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="flex gap-3 mt-5">
                            <button
                                onClick={() => setSchedulePickerData(null)}
                                className="flex-1 py-2.5 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
                            >
                                취소
                            </button>
                            <button
                                onClick={confirmAddSchedule}
                                disabled={addingScheduleId != null || !pickerDate}
                                className="flex-1 py-2.5 bg-primary-700 text-white text-xs font-black rounded-xl shadow-xl shadow-primary-700/20 hover:bg-primary-900 hover:scale-105 transition-all disabled:opacity-50 flex items-center justify-center gap-1.5"
                            >
                                {addingScheduleId != null ? (
                                    <><RefreshCw size={12} className="animate-spin" /> 추가 중...</>
                                ) : (
                                    <><CalendarPlus size={12} /> 추가</>
                                )}
                            </button>
                        </div>
                    </motion.div>
                </div>,
                document.body
            )}

            {/* ── 캘린더 추가 결과 모달 (성공/실패) ── */}
            {scheduleResult && createPortal(
                <div className="fixed inset-0 z-[150] flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
                        onClick={() => setScheduleResult(null)}
                    />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.9, y: 20 }}
                        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                        className="relative bg-white/90 dark:bg-neutral-900/90 backdrop-blur-xl rounded-2xl shadow-2xl w-full max-w-[340px] p-8 mx-4 border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex flex-col items-center text-center">
                            <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-4 ${
                                scheduleResult.success
                                    ? 'bg-success-bg dark:bg-success-bg'
                                    : 'bg-error-bg dark:bg-error-bg'
                            }`}>
                                {scheduleResult.success
                                    ? <CheckCircle2 size={32} className="text-success" />
                                    : <XCircle size={32} className="text-error" />
                                }
                            </div>
                            <h3 className="text-lg font-black text-neutral-900 dark:text-white tracking-tight mb-2">
                                {scheduleResult.success ? '추가 완료' : '추가 실패'}
                            </h3>
                            <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6 leading-relaxed">
                                {scheduleResult.message}
                            </p>
                            <button
                                onClick={() => setScheduleResult(null)}
                                className={`w-full py-3 text-sm font-extrabold rounded-xl shadow-lg transition-all ${
                                    scheduleResult.success
                                        ? 'bg-success text-white hover:bg-success/90'
                                        : 'bg-error text-white hover:bg-error/90'
                                }`}
                            >
                                확인
                            </button>
                        </div>
                    </motion.div>
                </div>,
                document.body
            )}
        </div>
    );
}
