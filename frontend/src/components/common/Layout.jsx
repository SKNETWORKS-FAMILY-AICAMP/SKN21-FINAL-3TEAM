import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useEffect } from 'react';
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

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Topbar />
      <main className={`flex-1 overflow-hidden flex flex-col ${isChatPage ? '' : 'px-8 pb-8'}`}>
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className={`flex-1 min-h-0 ${isChatPage ? '' : 'overflow-y-auto'}`}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
      <AIDock />
    </div>
  );
}
