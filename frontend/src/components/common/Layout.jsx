import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useLayoutEffect, useState, useRef, useCallback } from 'react';
import useUIStore from '../../store/uiStore';
import Topbar from './Topbar';
import AIDock from './AIDock';
import ErrorBoundary from './ErrorBoundary';
import AIChatPopup from '../chat/AIChatPopup';
import MessagePopup from '../messages/MessagePopup';
import RightSidebar from './RightSidebar';

const pageVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};

export default function Layout() {
  const location = useLocation();
  const isChatPage = location.pathname === '/chat';
  const topbarScheduleHidden = useUIStore((s) => s.dashboard?.topbarScheduleHidden);
  const [isScrolled, setIsScrolled] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [messageOpen, setMessageOpen] = useState(false);

  const mainRef = useRef(null);
  const motionRef = useRef(null);
  // handleScroll 클로저에서 최신 isChatPage 값을 참조하기 위한 ref
  const isChatPageRef = useRef(isChatPage);
  isChatPageRef.current = isChatPage;
  // topbar/페이지 헤더 높이 변화로 발생하는 scroll 이벤트를 무시하기 위한 플래그
  const resizingRef = useRef(false);
  const resizeTimerRef = useRef(null);
  const isScrolledRef = useRef(false);
  // 챗봇 방향 기반 감지용
  const prevScrollTopRef = useRef(0);
  // 챗봇 자동 스크롤 차단용 — ResizeObserver와 독립된 별도 플래그
  const navBlockRef = useRef(false);
  const navBlockTimerRef = useRef(null);

  // useLayoutEffect: paint 전 동기 실행 → 페이지 전환 시 isScrolled를 즉시 리셋
  useLayoutEffect(() => {
    setIsScrolled(false);
    isScrolledRef.current = false;
    if (location.pathname === '/chat') {
      navBlockRef.current = true;
      prevScrollTopRef.current = 0;
      clearTimeout(navBlockTimerRef.current);
      navBlockTimerRef.current = setTimeout(() => {
        // 자동 스크롤 완료 후의 실제 위치를 기준점으로 설정
        const chatScroll = document.querySelector('[data-main-scroll]');
        if (chatScroll) prevScrollTopRef.current = chatScroll.scrollTop;
        navBlockRef.current = false;
      }, 500);
    }
    return () => clearTimeout(navBlockTimerRef.current);
  }, [location.pathname]);

  useEffect(() => {
    prevScrollTopRef.current = 0;
    if (mainRef.current) mainRef.current.scrollTop = 0;
  }, [location.pathname]);

  useEffect(() => {
    const el = mainRef.current;
    if (!el) return;
    // main 크기가 바뀌면(topbar 높이 변화) 50ms 동안 scroll 이벤트 무시
    const ro = new ResizeObserver(() => {
      resizingRef.current = true;
      clearTimeout(resizeTimerRef.current);
      resizeTimerRef.current = setTimeout(() => {
        resizingRef.current = false;
      }, 50);
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      clearTimeout(resizeTimerRef.current);
    };
  }, []);

  const handleScroll = useCallback((e) => {
    if (e.target !== mainRef.current && !e.target.hasAttribute('data-main-scroll')) return;

    const { scrollTop } = e.target;
    const isChat = e.target !== mainRef.current;

    let newVal;
    if (isChat) {
      // 챗봇: 방향 기반 (스크롤 다운 → 줄어듦, 스크롤 업 → 커짐)
      const { scrollHeight, clientHeight } = e.target;
      const scrollableRange = scrollHeight - clientHeight;
      const delta = scrollTop - prevScrollTopRef.current;
      prevScrollTopRef.current = scrollTop; // 블록 중에도 항상 갱신
      if (navBlockRef.current) return;
      // scrollTop이 0이 됐는데 헤더가 숨겨진 경우 → resizing 중에도 항상 복원
      // (topbar 축소로 컨테이너가 커져 브라우저가 scrollTop을 0으로 자동 조정할 때)
      if (scrollTop === 0 && isScrolledRef.current) newVal = false;
      // 스크롤 가능 범위가 충분해야만 줄어듦 (topbar 44px + 여유 20px = 64px)
      else if (resizingRef.current) return;
      else if (delta > 5 && scrollableRange > 64) newVal = true;
      else if (delta < -5) newVal = false;
      else return;
    } else {
      // 일반 페이지: 위치 기반
      // 챗봇 페이지에서 main 엘리먼트 잔여 스크롤 이벤트(이전 페이지 scrollTop)를 무시
      if (resizingRef.current || isChatPageRef.current) return;
      newVal = scrollTop > 10;
    }

    if (newVal !== isScrolledRef.current) {
      // isScrolled 변경 시 topbar+페이지 헤더 높이 변화로 인한 scroll 이벤트를 150ms 차단
      resizingRef.current = true;
      clearTimeout(resizeTimerRef.current);
      resizeTimerRef.current = setTimeout(() => {
        resizingRef.current = false;
      }, 150);
      isScrolledRef.current = newVal;
    }
    setIsScrolled(newVal);
  }, []);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Topbar isScrolled={isScrolled} />
      <main
        ref={mainRef}
        onScrollCapture={handleScroll}
        className={`flex-1 min-h-0 relative transition-[padding] duration-300 ease-in-out ${isChatPage
          ? `overflow-hidden flex flex-col ${isScrolled ? 'pt-[76px]' : (topbarScheduleHidden ? 'pt-[96px]' : 'pt-[180px]')}`
          : `overflow-y-auto overflow-x-hidden ${topbarScheduleHidden ? 'pt-[100px]' : 'pt-[180px]'} px-4 md:px-8 pb-20`
          }`}
      >
        <AnimatePresence mode="wait">
          <motion.div
            ref={motionRef}
            key={location.pathname}
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className={isChatPage ? 'flex-1 min-h-0' : ''}
            onAnimationComplete={() => {
              if (motionRef.current) motionRef.current.style.transform = 'none';
            }}
          >
            <ErrorBoundary key={location.pathname}>
              <Outlet context={{ isScrolled }} />
            </ErrorBoundary>
          </motion.div>
        </AnimatePresence>
      </main>
      {!isChatPage && <AIDock />}

      {!isChatPage && (
        <RightSidebar
          chatOpen={chatOpen}
          setChatOpen={setChatOpen}
          messageOpen={messageOpen}
          setMessageOpen={setMessageOpen}
        />
      )}

      {!isChatPage && <AIChatPopup isOpen={chatOpen} onClose={() => setChatOpen(false)} />}
      <MessagePopup open={messageOpen} onClose={() => setMessageOpen(false)} />
    </div>
  );
}

