import { useRef, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useMotionValue, useSpring, useTransform, AnimatePresence } from 'framer-motion';
import { MessageSquare, FilePlus, FileText, Users2, Calendar } from 'lucide-react';

const features = [
    { id: 'chat', icon: MessageSquare, label: 'AI 챗봇', color: 'bg-primary-500', to: '/chat' },
    { id: 'doc-gen', icon: FilePlus, label: '문서 생성', color: 'bg-accent-500', to: '/document-generate' },
    { id: 'docs', icon: FileText, label: '문서 관리', color: 'bg-neutral-600', to: '/documents' },
    { id: 'meetings', icon: Users2, label: '회의 관리', color: 'bg-success', to: '/meetings' },
    { id: 'schedules', icon: Calendar, label: '일정 관리', color: 'bg-indigo-500', to: '/schedules' },
];

function DockIcon({ feature, mouseX }) {
    const ref = useRef(null);
    const navigate = useNavigate();

    const distance = useTransform(mouseX, (val) => {
        const bounds = ref.current?.getBoundingClientRect() ?? { x: 0, width: 0 };
        return val - bounds.x - bounds.width / 2;
    });

    const widthSync = useTransform(distance, [-150, 0, 150], [40, 80, 40]);
    const width = useSpring(widthSync, { mass: 0.1, stiffness: 150, damping: 12 });

    const [hovered, setHovered] = useState(false);

    return (
        <motion.div
            ref={ref}
            style={{ width }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            onClick={() => navigate(feature.to)}
            className="aspect-square rounded-full flex items-center justify-center cursor-pointer relative group"
        >
            <div className={`w-full h-full rounded-full ${feature.color} flex items-center justify-center text-white shadow-lg transition-transform duration-200 group-hover:scale-110`}>
                <feature.icon size="50%" />
            </div>

            <AnimatePresence>
                {hovered && (
                    <motion.div
                        initial={{ opacity: 0, y: 10, x: '-50%' }}
                        animate={{ opacity: 1, y: -45, x: '-50%' }}
                        exit={{ opacity: 0, y: 10, x: '-50%' }}
                        className="absolute left-1/2 px-2.5 py-1.5 bg-white/90 backdrop-blur-sm text-neutral-900 text-[11px] font-medium rounded-lg shadow-sm border border-neutral-200 whitespace-nowrap pointer-events-none"
                    >
                        {feature.label}
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}

export default function AIDock() {
    const mouseX = useMotionValue(Infinity);
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        const handleMouseMove = (e) => {
            // 화면 하단 80px 이내로 마우스가 들어오면 독을 표시
            if (e.clientY > window.innerHeight - 80) {
                setIsVisible(true);
            } else if (e.clientY < window.innerHeight - 150) {
                // 독에서 좀 더 멀어지면 다시 숨김 (사용 편의성 위해 여유 공간 둠)
                setIsVisible(false);
            }
        };

        window.addEventListener('mousemove', handleMouseMove);
        return () => window.removeEventListener('mousemove', handleMouseMove);
    }, []);

    return (
        <AnimatePresence>
            {isVisible && (
                <motion.div
                    initial={{ y: 100, x: '-50%', opacity: 0 }}
                    animate={{ y: 0, x: '-50%', opacity: 1 }}
                    exit={{ y: 100, x: '-50%', opacity: 0 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    className="fixed bottom-6 left-1/2 z-50"
                >
                    <motion.div
                        onMouseMove={(e) => mouseX.set(e.pageX)}
                        onMouseLeave={() => mouseX.set(Infinity)}
                        className="mx-auto flex h-16 items-end gap-4 rounded-[2.5rem] bg-white/5 backdrop-blur-xl border border-white/20 px-4 pb-3 shadow-2xl"
                    >
                        {features.map((feature) => (
                            <DockIcon key={feature.id} feature={feature} mouseX={mouseX} />
                        ))}
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
