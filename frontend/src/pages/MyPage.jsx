import { useState, useEffect } from 'react';
import {
    User, Mail, Users, MessageSquare, FileText, Calendar,
    Clock, StickyNote, Settings, Bell, Zap, ChevronRight,
    Trash2, Plus, Save, History, MessageCircle
} from 'lucide-react';
import useAuthStore from '../store/authStore';
import useUIStore from '../store/uiStore';
import useChatStore from '../store/chatStore';
import { listDocuments } from '../api/documents';
import { listSchedules } from '../api/schedules';
import { listSessions } from '../api/chat';

export default function MyPage() {
    const user = useAuthStore((s) => s.user);
    const { memos, addMemo, updateMemo, deleteMemo, settings, updateSettings } = useUIStore();
    const { sessions, fetchSessions } = useChatStore();

    const [stats, setStats] = useState({ chats: 0, docs: 0, schedules: 0 });
    const [recentDocs, setRecentDocs] = useState([]);
    const [recentSchedules, setRecentSchedules] = useState([]);
    const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'activity' | 'settings'

    useEffect(() => {
        const loadStats = async () => {
            try {
                const [docsResp, schedsResp, sessResp] = await Promise.all([
                    listDocuments(),
                    listSchedules(),
                    listSessions()
                ]);

                setStats({
                    docs: docsResp.data?.length || 0,
                    schedules: schedsResp.data?.length || 0,
                    chats: sessResp?.length || 0
                });

                setRecentDocs(docsResp.data?.slice(0, 3) || []);
                setRecentSchedules(schedsResp.data?.slice(0, 3) || []);
            } catch (e) {
                console.error('Failed to load MyPage data:', e);
            }
        };
        loadStats();
        fetchSessions(); // Chat sessions update
    }, [fetchSessions]);

    const toggleAiStyle = () => {
        const next = settings.aiStyle === 'detailed' ? 'concise' : 'detailed';
        updateSettings({ aiStyle: next });
    };

    const toggleNotifications = () => {
        updateSettings({ notifications: !settings.notifications });
    };

    return (
        <div className="max-w-6xl mx-auto py-8 px-4 space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* 1. 프로필 헤더 */}
            <section className="bg-white rounded-2xl border border-neutral-divider shadow-sm p-8 flex flex-col md:flex-row items-center gap-8">
                <div className="w-24 h-24 rounded-2xl bg-accent-500 flex items-center justify-center text-3xl font-bold text-white shadow-sm shrink-0">
                    {user?.name?.[0] || '?'}
                </div>
                <div className="flex-1 text-center md:text-left">
                    <h1 className="text-2xl font-bold text-neutral-main">{user?.name || '사용자'}</h1>
                    <div className="flex flex-wrap justify-center md:justify-start gap-4 mt-2 text-sm text-neutral-sub">
                        <span className="flex items-center gap-1.5"><Mail size={14} /> {user?.email}</span>
                        <span className="flex items-center gap-1.5"><Users size={14} /> {user?.team || '소속 팀 없음'}</span>
                        <span className="px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 text-[10px] font-bold uppercase tracking-wider">
                            {user?.is_admin ? 'Administrator' : 'General User'}
                        </span>
                    </div>
                </div>
                <button className="px-6 py-2.5 bg-neutral-main text-white rounded-xl text-sm font-semibold hover:bg-neutral-dark transition-all shrink-0">
                    프로필 수정
                </button>
            </section>

            {/* 메인 그리드 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                {/* 왼쪽: 통계 및 히스토리 */}
                <div className="lg:col-span-2 space-y-8">

                    {/* 2. 활동 요약 대시보드 */}
                    <div className="grid grid-cols-3 gap-4">
                        {[
                            { label: 'AI 대화', value: stats.chats, icon: MessageSquare, color: 'text-primary-600', bg: 'bg-primary-50' },
                            { label: '문서 생성', value: stats.docs, icon: FileText, color: 'text-accent-600', bg: 'bg-accent-50' },
                            { label: '남은 일정', value: stats.schedules, icon: Calendar, color: 'text-indigo-600', bg: 'bg-indigo-50' },
                        ].map((stat, i) => (
                            <div key={i} className="bg-surface-card p-6 rounded-2xl border border-neutral-divider shadow-sm hover:shadow-md transition-all">
                                <div className={`w-10 h-10 ${stat.bg} ${stat.color} rounded-xl flex items-center justify-center mb-4`}>
                                    <stat.icon size={20} />
                                </div>
                                <div className="text-2xl font-bold text-neutral-main">{stat.value}<span className="text-sm font-normal text-neutral-sub ml-1">건</span></div>
                                <div className="text-xs text-neutral-sub mt-1">{stat.label}</div>
                            </div>
                        ))}
                    </div>

                    {/* 3. 최근 작업 히스토리 */}
                    <section className="bg-surface-card rounded-2xl border border-neutral-divider shadow-sm p-6">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-lg font-bold text-neutral-main flex items-center gap-2">
                                <History size={18} className="text-primary-600" /> 최근 작업 및 히스토리
                            </h2>
                            <button className="text-xs text-primary-600 font-medium hover:underline">전체 보기</button>
                        </div>

                        <div className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {/* 최근 대화 */}
                                <div className="space-y-3">
                                    <h3 className="text-xs font-bold text-neutral-sub uppercase tracking-wider flex items-center gap-1.5">
                                        <MessageCircle size={12} /> 최근 AI 대화
                                    </h3>
                                    {sessions.slice(0, 3).map(s => (
                                        <a key={s.session_id} href={`/chat?session=${s.session_id}`} className="block p-3 bg-surface-hover rounded-xl border border-transparent hover:border-neutral-divider transition-all">
                                            <div className="text-sm font-medium text-neutral-main truncate">{s.name}</div>
                                            <div className="text-[10px] text-neutral-muted mt-1">{new Date(s.updated_at).toLocaleDateString()}</div>
                                        </a>
                                    ))}
                                    {sessions.length === 0 && <div className="text-xs text-neutral-muted py-4 text-center border border-dashed border-neutral-divider rounded-xl">대화 기록이 없습니다.</div>}
                                </div>

                                {/* 최근 문서 */}
                                <div className="space-y-3">
                                    <h3 className="text-xs font-bold text-neutral-sub uppercase tracking-wider flex items-center gap-1.5">
                                        <FileText size={12} /> 최근 생성 문서
                                    </h3>
                                    {recentDocs.map(d => (
                                        <div key={d.id} className="p-3 bg-surface-hover rounded-xl border border-transparent hover:border-neutral-divider transition-all flex items-center justify-between">
                                            <div className="truncate flex-1">
                                                <div className="text-sm font-medium text-neutral-main truncate">{d.name}</div>
                                                <div className="text-[10px] text-neutral-muted mt-1">{new Date(d.created_at).toLocaleDateString()}</div>
                                            </div>
                                            <ChevronRight size={14} className="text-neutral-muted" />
                                        </div>
                                    ))}
                                    {recentDocs.length === 0 && <div className="text-xs text-neutral-muted py-4 text-center border border-dashed border-neutral-divider rounded-xl">문서 기록이 없습니다.</div>}
                                </div>
                            </div>

                            {/* 메모 섹션 */}
                            <div className="pt-6 border-t border-neutral-divider mt-6">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-xs font-bold text-neutral-sub uppercase tracking-wider flex items-center gap-1.5">
                                        <StickyNote size={12} /> 개인 메모
                                    </h3>
                                    <button onClick={addMemo} className="w-6 h-6 rounded-full bg-primary-600 text-white flex items-center justify-center hover:bg-primary-700 transition-all shadow-sm">
                                        <Plus size={14} />
                                    </button>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {memos.slice(0, 4).map(m => (
                                        <div key={m.id} className="group relative bg-[#fffbe6] dark:bg-[#2c2c1e] p-4 rounded-xl border border-[#ffe58f] dark:border-[#595912] shadow-sm">
                                            <textarea
                                                value={m.text}
                                                onChange={(e) => updateMemo(m.id, e.target.value)}
                                                placeholder="메모를 입력하세요..."
                                                className="w-full h-20 bg-transparent text-sm text-neutral-main outline-none resize-none placeholder:text-neutral-muted/50"
                                            />
                                            <button
                                                onClick={() => deleteMemo(m.id)}
                                                className="absolute bottom-2 right-2 p-1.5 text-neutral-muted hover:text-error opacity-0 group-hover:opacity-100 transition-all"
                                            >
                                                <Trash2 size={12} />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </section>
                </div>

                {/* 오른쪽: 설정 */}
                <div className="space-y-8">

                    {/* 4. 개인화 설정 */}
                    <section className="bg-surface-card rounded-2xl border border-neutral-divider shadow-sm p-6">
                        <h2 className="text-lg font-bold text-neutral-main flex items-center gap-2 mb-6">
                            <Settings size={18} className="text-neutral-sub" /> 개인화 설정
                        </h2>

                        <div className="space-y-6">
                            {/* AI 스타일 */}
                            <div className="space-y-3">
                                <label className="text-xs font-bold text-neutral-sub uppercase tracking-wider">AI 답변 스타일</label>
                                <div className="flex p-1 bg-surface-hover rounded-xl border border-neutral-divider">
                                    <button
                                        onClick={() => updateSettings({ aiStyle: 'concise' })}
                                        className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all ${settings.aiStyle === 'concise' ? 'bg-white text-primary-700 shadow-sm' : 'text-neutral-sub hover:text-neutral-main'}`}
                                    >
                                        간결하게
                                    </button>
                                    <button
                                        onClick={() => updateSettings({ aiStyle: 'detailed' })}
                                        className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all ${settings.aiStyle === 'detailed' ? 'bg-white text-primary-700 shadow-sm' : 'text-neutral-sub hover:text-neutral-main'}`}
                                    >
                                        상세하게
                                    </button>
                                </div>
                                <p className="text-[10px] text-neutral-muted leading-relaxed">
                                    {settings.aiStyle === 'detailed'
                                        ? 'AI가 조항 원문과 풍부한 근거를 포함하여 상세히 답변합니다.'
                                        : '핵심 내용 위주로 빠르고 간결한 답변을 제공합니다.'}
                                </p>
                            </div>

                            {/* 알림 설정 */}
                            <div className="flex items-center justify-between py-4 border-t border-neutral-divider">
                                <div>
                                    <div className="text-sm font-bold text-neutral-main">시스템 알림</div>
                                    <div className="text-[10px] text-neutral-muted mt-0.5">문서 생성 완료 및 일정 알림 수신</div>
                                </div>
                                <button
                                    onClick={toggleNotifications}
                                    className={`relative w-11 h-6 rounded-full transition-colors duration-200 outline-none ${settings.notifications ? 'bg-primary-600' : 'bg-neutral-divider'}`}
                                >
                                    <div className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform duration-200 ${settings.notifications ? 'translate-x-5' : 'translate-x-0'}`} />
                                </button>
                            </div>

                            {/* 기타 설정 */}
                            <button className="w-full flex items-center justify-between p-4 bg-surface-hover rounded-xl text-sm font-medium text-neutral-main hover:bg-neutral-divider transition-all">
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 bg-neutral-divider rounded-lg flex items-center justify-center text-neutral-sub">
                                        <Zap size={16} />
                                    </div>
                                    단축키 관리
                                </div>
                                <ChevronRight size={16} className="text-neutral-muted" />
                            </button>
                        </div>

                        <div className="mt-8 pt-6 border-t border-neutral-divider">
                            <button className="w-full py-3 bg-primary-50 text-primary-700 rounded-xl text-sm font-bold hover:bg-primary-100 transition-all flex items-center justify-center gap-2 shadow-sm">
                                <Save size={16} /> 설정 저장하기
                            </button>
                        </div>
                    </section>

                </div>
            </div>
        </div>
    );
}
