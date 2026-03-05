import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Mail, Send, Inbox, Clock, Search, Trash2, Check, Eye, X,
} from 'lucide-react';
import { listMessages, sendMessage, markAsRead, deleteMessage, getUnreadCount } from '../api/messages';
import client from '../api/client';

export default function MessagesPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [box, setBox] = useState('inbox'); // inbox | sent
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [teamMembers, setTeamMembers] = useState([]);
  const [formData, setFormData] = useState({ receiver_id: '', content: '' });
  const [submitting, setSubmitting] = useState(false);

  const loadMessages = async () => {
    setLoading(true);
    try {
      const data = await listMessages(box);
      setItems(data);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const loadTeamMembers = async () => {
    try {
      const res = await client.get('/auth/all-members');
      setTeamMembers(res.data || []);
    } catch (err) {
      console.error('멤버 목록 로드 실패:', err?.response?.status, err?.message);
      setTeamMembers([]);
    }
  };

  useEffect(() => { loadMessages(); }, [box]);
  useEffect(() => { loadTeamMembers(); }, []);

  const handleExpand = async (item) => {
    if (expandedId === item.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(item.id);
    if (box === 'inbox' && !item.is_read) {
      try {
        await markAsRead(item.id);
        setItems(prev => prev.map(m => m.id === item.id ? { ...m, is_read: true } : m));
      } catch {}
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('이 쪽지를 삭제하시겠습니까?')) return;
    try {
      await deleteMessage(id);
      setItems(prev => prev.filter(m => m.id !== id));
      if (expandedId === id) setExpandedId(null);
    } catch (err) {
      alert(err.response?.data?.detail || '삭제에 실패했습니다.');
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!formData.receiver_id || !formData.content.trim()) return;
    setSubmitting(true);
    try {
      await sendMessage(Number(formData.receiver_id), formData.content.trim());
      setShowModal(false);
      setFormData({ receiver_id: '', content: '' });
      if (box === 'sent') await loadMessages();
    } catch (err) {
      alert(err.response?.data?.detail || '쪽지 전송에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  const filtered = items.filter(i => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      i.content.toLowerCase().includes(q) ||
      (i.sender_name || '').toLowerCase().includes(q) ||
      (i.receiver_name || '').toLowerCase().includes(q)
    );
  });

  const unreadCount = items.filter(i => !i.is_read).length;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-main flex items-center gap-3">
            <Mail className="text-accent-500" size={28} />
            쪽지함
          </h1>
          <p className="text-sm text-neutral-muted mt-1">동료에게 쪽지를 보내고 받을 수 있습니다</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2.5 bg-primary-500 hover:bg-primary-600 text-white text-sm font-semibold rounded-xl transition-colors shadow-sm"
        >
          + 쪽지 보내기
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {[
          { key: 'inbox', label: '받은 쪽지', icon: Inbox },
          { key: 'sent', label: '보낸 쪽지', icon: Send },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => { setBox(tab.key); setExpandedId(null); }}
            className={`px-4 py-2 text-sm font-semibold rounded-xl transition-all flex items-center gap-1.5 ${
              box === tab.key
                ? 'bg-primary-500 text-white shadow-sm'
                : 'bg-white dark:bg-neutral-800 text-neutral-sub hover:bg-neutral-50 dark:hover:bg-neutral-700 border border-neutral-200 dark:border-neutral-700'
            }`}
          >
            <tab.icon size={14} />
            {tab.label}
            {tab.key === 'inbox' && unreadCount > 0 && box === 'inbox' && (
              <span className="ml-1 text-xs px-1.5 py-0.5 rounded-full bg-white/20">{unreadCount}</span>
            )}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-muted" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="이름 또는 내용 검색..."
          className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm"
        />
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center h-40 text-neutral-muted">
          <Clock className="animate-spin mr-2" size={20} /> 로딩 중...
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 text-neutral-muted">
          <Mail className="mb-2 opacity-50" size={32} />
          <p className="text-sm">쪽지가 없습니다</p>
        </div>
      ) : (
        <div className="space-y-2">
          <AnimatePresence>
            {filtered.map((item, idx) => {
              const isExpanded = expandedId === item.id;
              const personName = box === 'inbox' ? item.sender_name : item.receiver_name;
              const personTeam = box === 'inbox' ? item.sender_team : item.receiver_team;
              const personAvatar = box === 'inbox' ? item.sender_avatar : item.receiver_avatar;
              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.2, delay: idx * 0.02 }}
                  className={`bg-white dark:bg-neutral-800 rounded-2xl border transition-shadow cursor-pointer ${
                    !item.is_read && box === 'inbox'
                      ? 'border-primary-300 dark:border-primary-700 shadow-md'
                      : 'border-neutral-100 dark:border-neutral-700 shadow-sm hover:shadow-md'
                  }`}
                >
                  <div
                    className="flex items-center gap-3 p-4"
                    onClick={() => handleExpand(item)}
                  >
                    {/* Avatar */}
                    {personAvatar ? (
                      <img src={personAvatar} alt="" className="w-9 h-9 rounded-full shrink-0" />
                    ) : (
                      <div className="w-9 h-9 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-sm font-bold text-primary-600 shrink-0">
                        {(personName || '?')[0]}
                      </div>
                    )}

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm ${!item.is_read && box === 'inbox' ? 'font-bold text-neutral-main' : 'font-medium text-neutral-sub'}`}>
                          {personName || '알 수 없음'}{personTeam ? ` (${personTeam})` : ''}
                        </span>
                        {!item.is_read && box === 'inbox' && (
                          <span className="w-2 h-2 rounded-full bg-primary-500 shrink-0" />
                        )}
                      </div>
                      <p className="text-xs text-neutral-muted truncate mt-0.5">{item.content}</p>
                    </div>

                    {/* Time + Actions */}
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-neutral-muted">
                        {item.created_at && new Date(item.created_at).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(item.id); }}
                        className="p-1.5 rounded-lg text-neutral-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-all"
                        title="삭제"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>

                  {/* Expanded Content */}
                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="px-4 pb-4 pt-0 border-t border-neutral-100 dark:border-neutral-700">
                          <div className="mt-3 text-sm text-neutral-main whitespace-pre-wrap leading-relaxed">
                            {item.content}
                          </div>
                          <div className="flex items-center gap-3 mt-3 text-xs text-neutral-muted">
                            <span>보낸 사람: {item.sender_name || '알 수 없음'}{item.sender_team ? ` (${item.sender_team})` : ''}</span>
                            <span>·</span>
                            <span>받는 사람: {item.receiver_name || '알 수 없음'}{item.receiver_team ? ` (${item.receiver_team})` : ''}</span>
                            {item.is_read && (
                              <>
                                <span>·</span>
                                <span className="flex items-center gap-0.5 text-green-500"><Eye size={12} /> 읽음</span>
                              </>
                            )}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}

      {/* Send Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
            onClick={() => setShowModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-neutral-900 rounded-2xl shadow-xl p-6 w-full max-w-md mx-4"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="text-lg font-bold text-neutral-main mb-4 flex items-center gap-2">
                <Send size={18} /> 쪽지 보내기
              </h3>
              <form onSubmit={handleSend} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-neutral-main mb-1">받는 사람</label>
                  <select
                    value={formData.receiver_id}
                    onChange={(e) => setFormData(prev => ({ ...prev, receiver_id: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm"
                    required
                  >
                    <option value="">선택하세요</option>
                    {teamMembers.map(m => (
                      <option key={m.id} value={m.id}>{m.name}{m.team ? ` (${m.team})` : ''}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-main mb-1">내용</label>
                  <textarea
                    value={formData.content}
                    onChange={(e) => setFormData(prev => ({ ...prev, content: e.target.value }))}
                    placeholder="쪽지 내용을 입력하세요"
                    rows={4}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm resize-none"
                    required
                  />
                </div>
                <div className="flex gap-2 pt-2">
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex-1 py-2 bg-primary-500 hover:bg-primary-600 text-white text-sm font-semibold rounded-lg transition-colors disabled:opacity-50"
                  >
                    {submitting ? '전송 중...' : '보내기'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="flex-1 py-2 bg-neutral-100 hover:bg-neutral-200 text-neutral-600 text-sm font-semibold rounded-lg transition-colors dark:bg-neutral-700 dark:hover:bg-neutral-600 dark:text-neutral-300"
                  >
                    취소
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
