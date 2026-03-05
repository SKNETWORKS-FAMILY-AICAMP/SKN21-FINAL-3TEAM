import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Mail, ChevronLeft, ChevronRight } from 'lucide-react';
import AIChatPopup from '../chat/AIChatPopup';
import MessagePopup from '../messages/MessagePopup';

export default function RightSidebar({ chatOpen, setChatOpen, messageOpen, setMessageOpen }) {
    const [isExpanded, setIsExpanded] = useState(false);

    // 외부 클릭 시 팝업 닫기 (필요 시)

    return (
        <div
            className="fixed right-0 bottom-24 z-[60] flex items-center h-auto overflow-visible select-none"
            onMouseEnter={() => setIsExpanded(true)}
            onMouseLeave={() => !chatOpen && !messageOpen && setIsExpanded(false)}
        >
            <motion.div
                initial={false}
                animate={isExpanded ? "expanded" : "collapsed"}
                variants={{
                    collapsed: { x: 0, opacity: 1, scale: 1 },
                    expanded: { x: 0, opacity: 1, scale: 1 }
                }}
                className="flex flex-col items-center justify-center bg-white/10 dark:bg-black/20 backdrop-blur-2xl shadow-xl transition-all duration-300"
                style={{
                    padding: isExpanded ? '6px' : '0px',
                    borderRadius: isExpanded ? '9999px 0 0 9999px' : '20px 0 0 20px',
                    borderWidth: isExpanded ? '1px' : '0px',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    minWidth: isExpanded ? '64px' : '16px',
                    minHeight: isExpanded ? 'auto' : '64px'
                }}
            >
                {!isExpanded ? (
                    /* 노치/핸들 영역 */
                    <div className="w-1 h-8 bg-white/40 rounded-full" />
                ) : (
                    /* 펼쳐진 아이콘 영역 */
                    <div className="flex flex-col gap-3">
                        {/* 쪽지 버튼 */}
                        <button
                            onClick={() => {
                                setMessageOpen(!messageOpen);
                                setChatOpen(false);
                            }}
                            className={`sidebar-trigger w-12 h-12 rounded-full flex items-center justify-center transition-all ${messageOpen
                                ? 'bg-primary-500 text-white shadow-lg'
                                : 'bg-white/20 dark:bg-white/5 text-neutral-700 dark:text-neutral-200 hover:bg-white/40'
                                }`}
                            title="쪽지"
                        >
                            <Mail size={22} />
                        </button>

                        {/* AI 챗봇 버튼 */}
                        <button
                            onClick={() => {
                                setChatOpen(!chatOpen);
                                setMessageOpen(false);
                            }}
                            className={`sidebar-trigger w-12 h-12 rounded-full flex items-center justify-center transition-all ${chatOpen
                                ? 'bg-primary-500 text-white shadow-lg'
                                : 'bg-white/20 dark:bg-white/5 text-neutral-700 dark:text-neutral-200 hover:bg-white/40'
                                }`}
                            title="AI 어시스턴트"
                        >
                            <MessageSquare size={22} />
                        </button>
                    </div>
                )}
            </motion.div>
        </div>
    );
}
