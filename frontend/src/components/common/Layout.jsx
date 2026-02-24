import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useLayoutEffect, useState, useRef, useCallback } from 'react';
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
  const mainRef = useRef(null);
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
      if (resizingRef.current || navBlockRef.current) return;
      // 스크롤 가능 범위가 충분해야만 줄어듦 (topbar 44px + 여유 20px = 64px)
      // → 줄어든 후에도 최소 20px 이상 남아 스크롤 올리기 가능
      if (delta > 5 && scrollableRange > 64) newVal = true;
      else if (delta < -5) newVal = false; // 위로 스크롤은 항상 허용
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
        className={`flex-1 min-h-0 ${isChatPage
            ? 'overflow-hidden flex flex-col'
            : 'overflow-y-auto px-8 pb-20'
          }`}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className={isChatPage ? 'flex-1 min-h-0' : ''}
          >
            <Outlet context={{ isScrolled }} />
          </motion.div>
        </AnimatePresence>
      </main>
      {!isChatPage && <AIDock />}
    </div>
  );
}
