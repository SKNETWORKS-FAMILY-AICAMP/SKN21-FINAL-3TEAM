import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Mail, ChevronLeft, ChevronRight } from 'lucide-react';
import AIChatPopup from '../chat/AIChatPopup';
import MessagePopup from '../messages/MessagePopup';

export default function RightSidebar({ chatOpen, setChatOpen, messageOpen, setMessageOpen }) {
    return (
        <div className="fixed right-8 bottom-8 z-[60] flex flex-col gap-3 select-none hidden">
            {/* 쪽지 버튼 */}
            <button
                onClick={() => {
                    setMessageOpen(!messageOpen);
                    setChatOpen(false);
                }}
                className={`sidebar-trigger w-14 h-14 rounded-full flex items-center justify-center transition-all shadow-lg ${messageOpen
                    ? 'bg-primary-500 text-white'
                    : 'bg-white/30 dark:bg-neutral-800/30 backdrop-blur-sm text-neutral-400 dark:text-neutral-400 hover:bg-primary-500 hover:text-white hover:shadow-xl'
                    }`}
                title="쪽지"
            >
                <Mail size={24} />
            </button>

            {/* AI 챗봇 버튼 */}
            <button
                onClick={() => {
                    setChatOpen(!chatOpen);
                    setMessageOpen(false);
                }}
                className={`sidebar-trigger w-14 h-14 rounded-full flex items-center justify-center transition-all shadow-lg ${chatOpen
                    ? 'bg-primary-500 text-white'
                    : 'bg-white/30 dark:bg-neutral-800/30 backdrop-blur-sm text-neutral-400 dark:text-neutral-400 hover:bg-primary-500 hover:text-white hover:shadow-xl'
                    }`}
                title="AI 어시스턴트"
            >
                <MessageSquare size={24} />
            </button>
        </div>
    );
}
