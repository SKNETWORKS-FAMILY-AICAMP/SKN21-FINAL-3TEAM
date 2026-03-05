import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mail, Send, Inbox, X, Trash2, Eye, ArrowLeft, Clock } from 'lucide-react';
import { listMessages, sendMessage, markAsRead, deleteMessage, getUnreadCount } from '../../api/messages';
import client from '../../api/client';

export default function MessagePopup({ open: externalOpen, onClose }) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = externalOpen !== undefined ? externalOpen : internalOpen;
  const setOpen = onClose || setInternalOpen;

  const [view, setView] = useState('list'); // list | compose | detail
  const [box, setBox] = useState('inbox');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [unread, setUnread] = useState(0);
  const [selectedMsg, setSelectedMsg] = useState(null);
  const [teamMembers, setTeamMembers] = useState([]);
  const [form, setForm] = useState({ receiver_id: '', content: '' });
  const [submitting, setSubmitting] = useState(false);

  const fetchUnread = async () => {
    try { setUnread(await getUnreadCount()); } catch { }
  };

  const loadMessages = async () => {
    setLoading(true);
    try { setItems(await listMessages(box)); } catch { setItems([]); }
    finally { setLoading(false); }
  };

  const loadTeamMembers = async () => {
    try {
      const res = await client.get('/auth/all-members');
      setTeamMembers(res.data || []);
    } catch (err) {
      console.error('멤버 목록 로드 실패:', err?.response?.status, err?.message);
    }
  };

  // 마운트 시 멤버 목록 미리 로드
  useEffect(() => {
    fetchUnread();
    loadTeamMembers();
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (open) { loadMessages(); if (teamMembers.length === 0) loadTeamMembers(); }
  }, [open, box]);

  const handleOpen = (msg) => {
    setSelectedMsg(msg);
    setView('detail');
    if (box === 'inbox' && !msg.is_read) {
      markAsRead(msg.id).then(() => {
        setItems(prev => prev.map(m => m.id === msg.id ? { ...m, is_read: true } : m));
        setUnread(prev => Math.max(0, prev - 1));
      }).catch(() => { });
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('삭제하시겠습니까?')) return;
    try {
      await deleteMessage(id);
      setItems(prev => prev.filter(m => m.id !== id));
      if (selectedMsg?.id === id) setView('list');
      fetchUnread();
    } catch (err) {
      alert(err.response?.data?.detail || '삭제 실패');
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!form.receiver_id || !form.content.trim()) return;
    setSubmitting(true);
    try {
      await sendMessage(Number(form.receiver_id), form.content.trim());
      setForm({ receiver_id: '', content: '' });
      setView('list');
      if (box === 'sent') loadMessages();
    } catch (err) {
      alert(err.response?.data?.detail || '전송 실패');
    } finally { setSubmitting(false); }
  };

  return (
    <>
      {/* Popup */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, x: 20, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-32 right-16 z-50 w-80 h-[28rem] bg-white dark:bg-neutral-900 rounded-2xl shadow-2xl border border-neutral-200 dark:border-neutral-700 flex flex-col overflow-hidden origin-right"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800">
              <div className="flex items-center gap-2">
                {view !== 'list' && (
                  <button onClick={() => setView('list')} className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300">
                    <ArrowLeft size={16} />
                  </button>
                )}
                <h3 className="text-sm font-bold text-neutral-main">
                  {view === 'compose' ? '쪽지 보내기' : view === 'detail' ? '쪽지 상세' : '쪽지함'}
                </h3>
              </div>
              <div className="flex items-center gap-1">
                {view === 'list' && (
                  <button
                    onClick={() => { setView('compose'); setForm({ receiver_id: '', content: '' }); }}
                    className="p-1.5 rounded-lg text-primary-500 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors"
                    title="쪽지 보내기"
                  >
                    <Send size={14} />
                  </button>
                )}
                <button onClick={() => setOpen(false)} className="p-1.5 rounded-lg text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors">
                  <X size={14} />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
              {view === 'list' && (
                <>
                  {/* Tabs */}
                  <div className="flex border-b border-neutral-100 dark:border-neutral-700">
                    {[
                      { key: 'inbox', label: '받은 쪽지', icon: Inbox },
                      { key: 'sent', label: '보낸 쪽지', icon: Send },
                    ].map(tab => (
                      <button
                        key={tab.key}
                        onClick={() => setBox(tab.key)}
                        className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-semibold transition-colors ${box === tab.key
                            ? 'text-primary-500 border-b-2 border-primary-500'
                            : 'text-neutral-muted hover:text-neutral-sub'
                          }`}
                      >
                        <tab.icon size={12} />
                        {tab.label}
                        {tab.key === 'inbox' && unread > 0 && (
                          <span className="ml-0.5 px-1.5 py-0.5 rounded-full bg-red-500 text-white text-[9px] font-bold">{unread}</span>
                        )}
                      </button>
                    ))}
                  </div>

                  {/* Message List */}
                  {loading ? (
                    <div className="flex items-center justify-center h-32 text-neutral-muted text-xs">
                      <Clock className="animate-spin mr-1.5" size={14} /> 로딩 중...
                    </div>
                  ) : items.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-32 text-neutral-muted">
                      <Mail className="mb-1.5 opacity-40" size={24} />
                      <p className="text-xs">쪽지가 없습니다</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-neutral-50 dark:divide-neutral-800">
                      {items.map(msg => {
                        const name = box === 'inbox' ? msg.sender_name : msg.receiver_name;
                        const team = box === 'inbox' ? msg.sender_team : msg.receiver_team;
                        const avatar = box === 'inbox' ? msg.sender_avatar : msg.receiver_avatar;
                        return (
                          <div
                            key={msg.id}
                            onClick={() => handleOpen(msg)}
                            className={`flex items-center gap-2.5 px-4 py-3 cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors ${!msg.is_read && box === 'inbox' ? 'bg-primary-50/50 dark:bg-primary-900/10' : ''
                              }`}
                          >
                            {avatar ? (
                              <img src={avatar} alt="" className="w-7 h-7 rounded-full shrink-0" />
                            ) : (
                              <div className="w-7 h-7 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-[10px] font-bold text-primary-600 shrink-0">
                                {(name || '?')[0]}
                              </div>
                            )}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className={`text-xs ${!msg.is_read && box === 'inbox' ? 'font-bold text-neutral-main' : 'font-medium text-neutral-sub'}`}>
                                  {name || '알 수 없음'}{team ? ` (${team})` : ''}
                                </span>
                                {!msg.is_read && box === 'inbox' && (
                                  <span className="w-1.5 h-1.5 rounded-full bg-primary-500" />
                                )}
                              </div>
                              <p className="text-[11px] text-neutral-muted truncate">{msg.content}</p>
                            </div>
                            <span className="text-[10px] text-neutral-muted shrink-0">
                              {msg.created_at && new Date(msg.created_at).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              )}

              {view === 'detail' && selectedMsg && (
                <div className="p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    {(box === 'inbox' ? selectedMsg.sender_avatar : selectedMsg.receiver_avatar) ? (
                      <img src={box === 'inbox' ? selectedMsg.sender_avatar : selectedMsg.receiver_avatar} alt="" className="w-8 h-8 rounded-full" />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-xs font-bold text-primary-600">
                        {((box === 'inbox' ? selectedMsg.sender_name : selectedMsg.receiver_name) || '?')[0]}
                      </div>
                    )}
                    <div>
                      <div className="text-xs font-semibold text-neutral-main">
                        {box === 'inbox' ? selectedMsg.sender_name : selectedMsg.receiver_name}{(box === 'inbox' ? selectedMsg.sender_team : selectedMsg.receiver_team) ? ` (${box === 'inbox' ? selectedMsg.sender_team : selectedMsg.receiver_team})` : ''}
                      </div>
                      <div className="text-[10px] text-neutral-muted">
                        {selectedMsg.created_at && new Date(selectedMsg.created_at).toLocaleString('ko-KR')}
                      </div>
                    </div>
                  </div>
                  <div className="text-sm text-neutral-main whitespace-pre-wrap leading-relaxed bg-neutral-50 dark:bg-neutral-800 rounded-xl p-3">
                    {selectedMsg.content}
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-neutral-muted">
                    <span>보낸 사람: {selectedMsg.sender_name}{selectedMsg.sender_team ? ` (${selectedMsg.sender_team})` : ''} → 받는 사람: {selectedMsg.receiver_name}{selectedMsg.receiver_team ? ` (${selectedMsg.receiver_team})` : ''}</span>
                    {selectedMsg.is_read && <span className="flex items-center gap-0.5 text-green-500"><Eye size={10} /> 읽음</span>}
                  </div>
                  <button
                    onClick={() => handleDelete(selectedMsg.id)}
                    className="w-full py-2 text-xs font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors flex items-center justify-center gap-1"
                  >
                    <Trash2 size={12} /> 삭제
                  </button>
                </div>
              )}

              {view === 'compose' && (
                <form onSubmit={handleSend} className="p-4 space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-neutral-main mb-1">받는 사람</label>
                    <select
                      value={form.receiver_id}
                      onChange={(e) => setForm(prev => ({ ...prev, receiver_id: e.target.value }))}
                      className="w-full px-3 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs"
                      required
                    >
                      <option value="">선택하세요</option>
                      {teamMembers.map(m => (
                        <option key={m.id} value={m.id}>{m.name}{m.team ? ` (${m.team})` : ''}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-neutral-main mb-1">내용</label>
                    <textarea
                      value={form.content}
                      onChange={(e) => setForm(prev => ({ ...prev, content: e.target.value }))}
                      placeholder="쪽지 내용을 입력하세요"
                      rows={5}
                      className="w-full px-3 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-xs resize-none"
                      required
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={submitting}
                      className="flex-1 py-2 bg-primary-500 hover:bg-primary-600 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50"
                    >
                      {submitting ? '전송 중...' : '보내기'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setView('list')}
                      className="flex-1 py-2 bg-neutral-100 hover:bg-neutral-200 text-neutral-600 text-xs font-semibold rounded-lg transition-colors dark:bg-neutral-700 dark:hover:bg-neutral-600 dark:text-neutral-300"
                    >
                      취소
                    </button>
                  </div>
                </form>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
