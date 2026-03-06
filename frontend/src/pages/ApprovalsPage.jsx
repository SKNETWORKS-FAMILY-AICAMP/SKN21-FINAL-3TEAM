import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Check, X, Clock, Coffee, GitPullRequest, FileText, FileSignature,
  Filter, Search, BellRing, CheckCircle2, XCircle, Trash2, Download, Paperclip, Eye,
  Home, DoorOpen, Palette, Award, Receipt, Rocket, Server, ShieldCheck
} from 'lucide-react';
import { listApprovals, createApproval, approveRequest, rejectRequest, deleteApproval, downloadApprovalFile, getApprovalFileBlobUrl } from '../api/approvals';
import client from '../api/client';

const typeConfig = {
  leave: { icon: Coffee, color: 'text-orange-500 bg-orange-100 dark:bg-orange-900/30', label: '연차/반차 신청' },
  remote: { icon: Home, color: 'text-teal-500 bg-teal-100 dark:bg-teal-900/30', label: '재택근무 신청' },
  room: { icon: DoorOpen, color: 'text-indigo-500 bg-indigo-100 dark:bg-indigo-900/30', label: '회의실 예약' },
  design: { icon: Palette, color: 'text-pink-500 bg-pink-100 dark:bg-pink-900/30', label: '디자인 에셋 요청' },
  certificate: { icon: Award, color: 'text-yellow-500 bg-yellow-100 dark:bg-yellow-900/30', label: '증명서 발급 요청' },
  budget: { icon: Receipt, color: 'text-purple-500 bg-purple-100 dark:bg-purple-900/30', label: '결재 요청' },
  review: { icon: GitPullRequest, color: 'text-blue-500 bg-blue-100 dark:bg-blue-900/30', label: 'PR 리뷰 요청' },
  deploy: { icon: Rocket, color: 'text-green-500 bg-green-100 dark:bg-green-900/30', label: '배포 승인 요청' },
  infra: { icon: Server, color: 'text-slate-500 bg-slate-100 dark:bg-slate-900/30', label: '인프라/권한 신청' },
  security: { icon: ShieldCheck, color: 'text-red-500 bg-red-100 dark:bg-red-900/30', label: '보안 예외 처리' },
};
const defaultTypeConfig = { icon: FileSignature, color: 'text-gray-500 bg-gray-100 dark:bg-gray-900/30', label: '요청' };

const statusConfig = {
  pending: { label: 'Pending', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400', icon: Clock },
  approved: { label: 'Approved', color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400', icon: CheckCircle2 },
  rejected: { label: 'Rejected', color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400', icon: XCircle },
};

export default function ApprovalsPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all / pending / approved / rejected
  const [typeFilter, setTypeFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({ type: 'leave', title: '', detail: '' });
  const [formFile, setFormFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [detailItem, setDetailItem] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      // status별로 나눠서 요청 (pending은 기본, approved/rejected도 가져오기)
      const [pendingRes, approvedRes, rejectedRes] = await Promise.all([
        client.get('/approvals/', { params: { status: 'pending' } }).catch(() => ({ data: [] })),
        client.get('/approvals/history', { params: { status: 'approved' } }).catch(() => ({ data: [] })),
        client.get('/approvals/history', { params: { status: 'rejected' } }).catch(() => ({ data: [] })),
      ]);
      const all = [
        ...(Array.isArray(pendingRes.data) ? pendingRes.data : []),
        ...(Array.isArray(approvedRes.data) ? approvedRes.data : []),
        ...(Array.isArray(rejectedRes.data) ? rejectedRes.data : []),
      ];
      setItems(all);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const handleApproval = async (id, approve) => {
    try {
      if (approve) await approveRequest(id);
      else await rejectRequest(id);
      await loadAll();
    } catch (err) {
      console.error('Action failed', err);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('이 요청을 삭제하시겠습니까?')) return;
    try {
      await deleteApproval(id);
      await loadAll();
    } catch (err) {
      const msg = err.response?.data?.detail || '삭제에 실패했습니다.';
      alert(msg);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.title.trim()) return;
    setSubmitting(true);
    try {
      await createApproval({ type: formData.type, title: formData.title.trim(), detail: formData.detail.trim() || null }, formFile);
      setShowModal(false);
      setFormData({ type: 'leave', title: '', detail: '' });
      setFormFile(null);
      await loadAll();
    } catch (err) {
      console.error('Approval create error:', err.response?.status, err.response?.data, err);
      alert('요청 생성에 실패했습니다. (' + (err.response?.data?.detail || err.message) + ')');
    } finally {
      setSubmitting(false);
    }
  };

  const filtered = items.filter(i => {
    if (filter !== 'all' && i.status !== filter) return false;
    if (typeFilter !== 'all' && i.type !== typeFilter) return false;
    if (search && !i.title.toLowerCase().includes(search.toLowerCase()) && !(i.requester_name || '').toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const counts = {
    all: items.length,
    pending: items.filter(i => i.status === 'pending').length,
    approved: items.filter(i => i.status === 'approved').length,
    rejected: items.filter(i => i.status === 'rejected').length,
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-main flex items-center gap-3">
            <BellRing className="text-accent-500" size={28} />
            Approval Requests
          </h1>
          <p className="text-sm text-neutral-muted mt-1">모든 결재/승인 요청을 확인하고 관리합니다</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2.5 bg-primary-500 hover:bg-primary-600 text-white text-sm font-semibold rounded-xl transition-colors shadow-sm"
        >
          + 새 요청
        </button>
      </div>

      {/* Status Tabs */}
      <div className="flex gap-2">
        {[
          { key: 'all', label: '전체' },
          { key: 'pending', label: 'Pending' },
          { key: 'approved', label: 'Approved' },
          { key: 'rejected', label: 'Rejected' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={`px-4 py-2 text-sm font-semibold rounded-xl transition-all ${filter === tab.key
                ? 'bg-primary-500 text-white shadow-sm'
                : 'bg-white dark:bg-neutral-800 text-neutral-sub hover:bg-neutral-50 dark:hover:bg-neutral-700 border border-neutral-200 dark:border-neutral-700'
              }`}
          >
            {tab.label}
            <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${filter === tab.key ? 'bg-white/20' : 'bg-neutral-100 dark:bg-neutral-700'
              }`}>
              {counts[tab.key]}
            </span>
          </button>
        ))}
      </div>

      {/* Filters Row */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="제목 또는 요청자 검색..."
            className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-neutral-muted" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2.5 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm"
          >
            <option value="all">모든 유형</option>
            <option value="leave">연차/반차 신청</option>
            <option value="remote">재택근무 신청</option>
            <option value="room">회의실 예약</option>
            <option value="design">디자인 에셋 요청</option>
            <option value="certificate">증명서 발급 요청</option>
            <option value="budget">결재 요청</option>
            <option value="review">PR 리뷰 요청</option>
            <option value="deploy">배포 승인 요청</option>
            <option value="infra">인프라/권한 신청</option>
            <option value="security">보안 예외 처리</option>
          </select>
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center h-40 text-neutral-muted">
          <Clock className="animate-spin mr-2" size={20} /> 로딩 중...
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 text-neutral-muted">
          <Check className="mb-2 opacity-50" size={32} />
          <p className="text-sm">표시할 요청이 없습니다</p>
        </div>
      ) : (
        <div className="space-y-3">
          <AnimatePresence>
            {filtered.map((item, idx) => {
              const cfg = typeConfig[item.type] || defaultTypeConfig;
              const stCfg = statusConfig[item.status] || statusConfig.pending;
              const IconComp = cfg.icon;
              const StatusIcon = stCfg.icon;
              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.2, delay: idx * 0.03 }}
                  className="bg-white/40 dark:bg-white/[0.05] backdrop-blur-md p-5 rounded-2xl border border-white/20 dark:border-white/10 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => setDetailItem(item)}
                >
                  <div className="flex items-start justify-between gap-4">
                    {/* Left: Info */}
                    <div className="flex items-start gap-4 flex-1 min-w-0">
                      <div className={`p-2.5 rounded-xl shrink-0 ${cfg.color}`}>
                        <IconComp size={20} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-bold text-neutral-sub px-2 py-0.5 bg-neutral-50 dark:bg-neutral-700 rounded-full">
                            {cfg.label}
                          </span>
                          <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1 ${stCfg.color}`}>
                            <StatusIcon size={12} />
                            {stCfg.label}
                          </span>
                        </div>
                        <h3 className="text-sm font-semibold text-neutral-main truncate">{item.title}</h3>
                        {item.detail && (
                          <p className="text-xs text-neutral-muted mt-0.5">{item.detail}</p>
                        )}
                        {item.file_name && (
                          <button
                            onClick={(e) => { e.stopPropagation(); downloadApprovalFile(item.id, item.file_name); }}
                            className="inline-flex items-center gap-1 text-xs text-primary-500 hover:text-primary-600 mt-1"
                          >
                            <Paperclip size={12} /> {item.file_name}
                          </button>
                        )}
                        <div className="flex items-center gap-2 mt-2">
                          {item.requester_avatar ? (
                            <img src={item.requester_avatar} alt="" className="w-5 h-5 rounded-full" />
                          ) : (
                            <div className="w-5 h-5 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-[10px] font-bold text-primary-600">
                              {(item.requester_name || '?')[0]}
                            </div>
                          )}
                          <span className="text-xs text-neutral-sub">{item.requester_name || '알 수 없음'}</span>
                          {item.target_team && (
                            <span className="text-xs text-neutral-muted">· {item.target_team}</span>
                          )}
                          {item.created_at && (
                            <span className="text-xs text-neutral-muted">· {new Date(item.created_at).toLocaleDateString('ko-KR')}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Right: Actions */}
                    <div className="flex gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
                      {item.status === 'pending' && (
                        <>
                          <button
                            onClick={() => handleApproval(item.id, true)}
                            className="flex items-center gap-1 px-3 py-2 bg-green-50 hover:bg-green-500 text-green-600 hover:text-white text-xs font-semibold rounded-lg transition-all"
                          >
                            <Check size={14} /> Approve
                          </button>
                          <button
                            onClick={() => handleApproval(item.id, false)}
                            className="flex items-center gap-1 px-3 py-2 bg-red-50 hover:bg-red-500 text-red-600 hover:text-white text-xs font-semibold rounded-lg transition-all"
                          >
                            <X size={14} /> Reject
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="flex items-center gap-1 px-2.5 py-2 bg-neutral-50 hover:bg-red-500 text-neutral-400 hover:text-white text-xs font-semibold rounded-lg transition-all dark:bg-neutral-700 dark:hover:bg-red-500"
                        title="삭제"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}

      {/* 상세 보기 모달 */}
      <AnimatePresence>
        {detailItem && (() => {
          const cfg = typeConfig[detailItem.type] || defaultTypeConfig;
          const stCfg = statusConfig[detailItem.status] || statusConfig.pending;
          const IconComp = cfg.icon;
          const StatusIcon = stCfg.icon;
          const isImage = detailItem.file_name && /\.(png|jpg|jpeg|gif|webp)$/i.test(detailItem.file_name);
          const isPdf = detailItem.file_name && /\.pdf$/i.test(detailItem.file_name);
          return (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
              onClick={() => setDetailItem(null)}
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2.5rem] shadow-2xl p-8 w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto border border-white/40 dark:border-white/10"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-3">
                    <div className={`p-2.5 rounded-xl ${cfg.color}`}>
                      <IconComp size={22} />
                    </div>
                    <div>
                      <span className="text-xs font-bold text-neutral-sub">{cfg.label}</span>
                      <h3 className="text-lg font-bold text-neutral-main">{detailItem.title}</h3>
                    </div>
                  </div>
                  <button onClick={() => setDetailItem(null)} className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-400 hover:text-neutral-600 transition-colors">
                    <X size={20} />
                  </button>
                </div>

                {/* Status */}
                <div className="mb-4">
                  <span className={`inline-flex items-center gap-1 text-xs font-bold px-3 py-1 rounded-full ${stCfg.color}`}>
                    <StatusIcon size={14} />
                    {stCfg.label}
                  </span>
                </div>

                {/* Requester */}
                <div className="flex items-center gap-3 mb-4 p-3 bg-neutral-50 dark:bg-neutral-800 rounded-xl">
                  {detailItem.requester_avatar ? (
                    <img src={detailItem.requester_avatar} alt="" className="w-9 h-9 rounded-full" />
                  ) : (
                    <div className="w-9 h-9 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-sm font-bold text-primary-600">
                      {(detailItem.requester_name || '?')[0]}
                    </div>
                  )}
                  <div>
                    <p className="text-sm font-semibold text-neutral-main">{detailItem.requester_name || '알 수 없음'}</p>
                    <div className="flex items-center gap-2 text-xs text-neutral-muted">
                      {detailItem.target_team && <span>{detailItem.target_team}</span>}
                      {detailItem.created_at && <span>· {new Date(detailItem.created_at).toLocaleString('ko-KR')}</span>}
                    </div>
                  </div>
                </div>

                {/* Detail */}
                <div className="mb-4">
                  <label className="block text-xs font-semibold text-neutral-sub mb-1">상세 내용</label>
                  <div className="p-3 bg-neutral-50 dark:bg-neutral-800 rounded-xl text-sm text-neutral-main whitespace-pre-wrap min-h-[60px]">
                    {detailItem.detail || '(내용 없음)'}
                  </div>
                </div>

                {/* Attachment */}
                {detailItem.file_name && (
                  <div className="mb-5">
                    <label className="block text-xs font-semibold text-neutral-sub mb-2">첨부파일</label>
                    <div className="flex items-center gap-2 p-3 bg-neutral-50 dark:bg-neutral-800 rounded-xl">
                      <Paperclip size={16} className="text-neutral-muted shrink-0" />
                      <span className="text-sm text-neutral-main truncate flex-1">{detailItem.file_name}</span>
                      {(isImage || isPdf) && (
                        <button
                          onClick={async () => { const url = await getApprovalFileBlobUrl(detailItem.id); setPreviewUrl(url); }}
                          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-primary-500 hover:text-primary-600 bg-primary-50 hover:bg-primary-100 dark:bg-primary-900/20 dark:hover:bg-primary-900/40 rounded-lg transition-colors"
                        >
                          <Eye size={14} /> 미리보기
                        </button>
                      )}
                      <button
                        onClick={() => downloadApprovalFile(detailItem.id, detailItem.file_name)}
                        className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-green-600 hover:text-green-700 bg-green-50 hover:bg-green-100 dark:bg-green-900/20 dark:hover:bg-green-900/40 rounded-lg transition-colors"
                      >
                        <Download size={14} /> 다운로드
                      </button>
                    </div>
                  </div>
                )}

                {/* Actions */}
                {detailItem.status === 'pending' && (
                  <div className="flex gap-2">
                    <button
                      onClick={async () => { await handleApproval(detailItem.id, true); setDetailItem(null); }}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-green-500 hover:bg-green-600 text-white text-sm font-semibold rounded-xl transition-colors"
                    >
                      <Check size={16} /> Approve
                    </button>
                    <button
                      onClick={async () => { await handleApproval(detailItem.id, false); setDetailItem(null); }}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-red-500 hover:bg-red-600 text-white text-sm font-semibold rounded-xl transition-colors"
                    >
                      <X size={16} /> Reject
                    </button>
                  </div>
                )}
              </motion.div>
            </motion.div>
          );
        })()}
      </AnimatePresence>

      {/* 파일 미리보기 모달 */}
      <AnimatePresence>
        {previewUrl && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60"
            onClick={() => setPreviewUrl(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-2xl shadow-2xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden flex flex-col border border-white/40 dark:border-white/10"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between p-4 border-b border-neutral-200 dark:border-neutral-700">
                <span className="text-sm font-semibold text-neutral-main">파일 미리보기</span>
                <div className="flex items-center gap-2">
                  {detailItem && (
                    <button
                      onClick={() => downloadApprovalFile(detailItem.id, detailItem.file_name)}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-green-600 bg-green-50 hover:bg-green-100 rounded-lg transition-colors"
                    >
                      <Download size={14} /> 다운로드
                    </button>
                  )}
                  <button onClick={() => { if (previewUrl) window.URL.revokeObjectURL(previewUrl); setPreviewUrl(null); }} className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-400 hover:text-neutral-600 transition-colors">
                    <X size={20} />
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-neutral-50 dark:bg-neutral-800 min-h-[400px]">
                {detailItem?.file_name && /\.(png|jpg|jpeg|gif|webp)$/i.test(detailItem.file_name) ? (
                  <img src={previewUrl} alt="미리보기" className="max-w-full max-h-[70vh] object-contain rounded-lg" />
                ) : detailItem?.file_name && /\.pdf$/i.test(detailItem.file_name) ? (
                  <iframe src={previewUrl} className="w-full h-[70vh] rounded-lg border-0" title="PDF 미리보기" />
                ) : (
                  <div className="text-center text-neutral-muted space-y-3">
                    <FileText size={48} className="mx-auto opacity-40" />
                    <p className="text-sm">이 파일 형식은 브라우저에서 미리보기를 지원하지 않습니다.</p>
                    {detailItem && (
                      <button
                        onClick={() => downloadApprovalFile(detailItem.id, detailItem.file_name)}
                        className="inline-flex items-center gap-1.5 px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white text-sm font-semibold rounded-xl transition-colors"
                      >
                        <Download size={16} /> 파일 다운로드
                      </button>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 새 요청 모달 */}
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
              className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2.5rem] shadow-2xl p-8 w-full max-w-md mx-4 border border-white/40 dark:border-white/10"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="text-lg font-bold text-neutral-main mb-4">새 요청 올리기</h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-neutral-main mb-1">유형</label>
                  <select
                    value={formData.type}
                    onChange={(e) => setFormData(prev => ({ ...prev, type: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm"
                  >
                    <option value="leave">연차/반차 신청</option>
                    <option value="remote">재택근무 신청</option>
                    <option value="room">회의실 예약</option>
                    <option value="design">디자인 에셋 요청</option>
                    <option value="certificate">증명서 발급 요청</option>
                    <option value="budget">결재 요청</option>
                    <option value="review">PR 리뷰 요청</option>
                    <option value="deploy">배포 승인 요청</option>
                    <option value="infra">인프라/권한 신청</option>
                    <option value="security">보안 예외 처리</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-main mb-1">제목</label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                    placeholder="요청 제목을 입력하세요"
                    className="w-full px-3 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-main mb-1">상세 내용</label>
                  <textarea
                    value={formData.detail}
                    onChange={(e) => setFormData(prev => ({ ...prev, detail: e.target.value }))}
                    placeholder="상세 내용을 입력하세요 (선택)"
                    rows={3}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm resize-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-main mb-1">첨부파일 (선택)</label>
                  <input
                    type="file"
                    accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg,.gif,.webp"
                    onChange={(e) => setFormFile(e.target.files[0] || null)}
                    className="w-full text-sm text-neutral-sub file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-600 hover:file:bg-primary-100 dark:file:bg-primary-900/30 dark:file:text-primary-400"
                  />
                  {formFile && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-neutral-muted">
                      <Paperclip size={12} />
                      <span className="truncate">{formFile.name}</span>
                      <button type="button" onClick={() => setFormFile(null)} className="ml-1 p-0.5 rounded hover:bg-red-100 text-red-400 hover:text-red-600 transition-colors">
                        <X size={14} />
                      </button>
                    </div>
                  )}
                </div>
                <div className="flex gap-3 pt-6">
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex-1 py-4 bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 text-xs font-black rounded-xl shadow-xl hover:scale-105 active:scale-95 transition-all disabled:opacity-50"
                  >
                    {submitting ? '제출 중...' : '요청 제출'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="flex-1 py-4 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
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
