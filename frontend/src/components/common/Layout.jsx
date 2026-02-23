import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useState, useCallback } from 'react';
import Topbar from './Topbar';
import AIDock from './AIDock';

const pageVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};

export default function Layout() {
  const location = useLocation();
  const isChatPage = location.pathname === '/chat';
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    window.scrollTo(0, 0);
    setIsScrolled(false);
  }, [location.pathname]);

  const handleScroll = useCallback((e) => {
    if (!e.target.hasAttribute('data-main-scroll')) return;
    setIsScrolled(e.target.scrollTop > 10);
  }, []);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Topbar isScrolled={isScrolled} />
      <main className={`flex-1 overflow-hidden flex flex-col ${isChatPage ? '' : 'px-8 pb-8'}`} onScrollCapture={handleScroll}>
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className={`flex-1 min-h-0 ${isChatPage ? '' : 'overflow-y-auto'}`}
            data-main-scroll=""
          >
            <Outlet context={{ isScrolled }} />
          </motion.div>
        </AnimatePresence>
      </main>
      <AIDock />
    </div>
  );
}
