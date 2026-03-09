import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useState, useRef } from 'react';
import useAuthStore from '../../store/authStore';
import { Bell, Calendar, Video, ArrowUpRight, LogOut, User, ChevronDown } from 'lucide-react';
import { listSchedules } from '../../api/schedules';
import dayjs from 'dayjs';

export default function Header() {
  const _user = useAuthStore((s) => s.user);
  const _logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [todaySchedules, setTodaySchedules] = useState([]);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const profileRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (profileRef.current && !profileRef.current.contains(e.target)) {
        setIsProfileOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const fetchTodaySchedules = async () => {
      try {
        const res = await listSchedules({ include_team: true });
        const all = res.data || [];
        const todayStr = dayjs().format('YYYY-MM-DD');
        const todays = all
          .filter(s => dayjs(s.start_time).format('YYYY-MM-DD') === todayStr)
          .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
        setTodaySchedules(todays);
      } catch (err) {
        console.error('Failed to fetch schedules', err);
      }
    };
    fetchTodaySchedules();
  }, []);

  return (
    <header className="flex justify-between items-center py-4 px-8 sticky top-0 bg-surface-main z-10 w-full shrink-0">
      
      {/* Empty space left to balance the center */}
      <div className="flex-1" />

      {/* Middle: Schedule Timeline Widget */}
      <div className="flex-[2] flex justify-center w-full">
        <div className="bg-surface-card border border-neutral-divider text-neutral-main rounded-full flex items-center p-2 w-full max-w-[850px] shadow-sm">
          {/* Label section */}
          <div className="flex items-center gap-3 px-6 py-2 whitespace-nowrap">
            <span className="text-base font-extrabold tracking-tight text-neutral-main">Your Schedule</span>
            <div className="bg-surface-sub rounded-full px-4 py-1.5 flex items-center gap-2 border border-neutral-divider">
              <Calendar size={14} className="text-neutral-muted" />
              <span className="text-sm text-neutral-sub font-semibold">{dayjs().format('DD MMMM')}</span>
            </div>
          </div>

          {/* Timeline Track (Light Background) */}
          <div className="flex-1 bg-surface-sub/80 rounded-full flex items-center ml-2 border border-neutral-divider shadow-inner relative overflow-hidden h-[52px]">
            {todaySchedules.length > 0 ? (
              <>
                {/* Active Event Block (Point Color) */}
                <div className="bg-[#5A768A] h-[48px] m-[2px] rounded-full flex items-center justify-between text-white px-5 min-w-[300px] w-[60%] relative z-10 shadow-sm border border-white/10">
                  <div className="flex items-center gap-4 w-full animate-fade-in relative z-10">
                    <div className="flex -space-x-1 items-center">
                       <div className="h-8 w-8 rounded-full bg-white/20 border border-white/30 flex items-center justify-center text-[10px] font-bold text-white shadow-sm backdrop-blur-sm z-10">Me</div>
                       {(todaySchedules[0].schedule_type === 'meeting' || todaySchedules[0].attendees > 0) && (
                         <div className="h-8 w-8 rounded-full bg-white/10 border border-white/20 flex items-center justify-center text-[10px] font-bold text-white/90 backdrop-blur-sm shadow-sm">T</div>
                       )}
                    </div>
                    
                    <div className="flex items-center gap-4 flex-1">
                      <div className="flex flex-col border-l border-white/20 pl-3">
                        <span className="text-[10px] font-bold text-white/80 leading-none">START</span>
                        <span className="text-[13px] font-bold text-white tracking-wide mt-0.5">{dayjs(todaySchedules[0].start_time).format('h:mm A')}</span>
                      </div>
                      
                      <div className="flex-1 flex justify-center">
                        <span className="text-sm font-extrabold truncate max-w-[150px] text-white tracking-wide">{todaySchedules[0].title}</span>
                      </div>
                    </div>

                    {todaySchedules[0].meet_link && (
                      <a href={todaySchedules[0].meet_link} target="_blank" rel="noreferrer" className="w-8 h-8 flex items-center justify-center bg-surface-card border border-transparent hover:border-white/30 text-primary-700 rounded-full transition-all shrink-0 shadow-sm">
                        <Video size={14} />
                      </a>
                    )}
                  </div>
                  
                  {/* Current Time Indicator on the edge of the block */}
                  <div className="absolute -top-1.5 -right-3 bg-neutral-800 text-white text-[10px] font-bold px-2 py-0.5 rounded-full z-20 shadow-md transform -translate-x-1/2 flex items-center gap-1">
                     <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                     {dayjs().format('h:mm a')}
                  </div>
                </div>
                
                {/* Upcoming Next Event Label outside the colored block */}
                {todaySchedules.length > 1 && (
                  <div className="absolute right-6 top-1/2 -translate-y-1/2 flex items-center gap-4 animate-fade-in">
                    <span className="text-[13px] font-bold text-neutral-400">{dayjs(todaySchedules[1].start_time).format('h:mm A')}</span>
                    <div className="flex -space-x-1 opacity-60 grayscale">
                       <div className="h-7 w-7 rounded-full bg-neutral-divider border border-surface-card flex items-center justify-center text-[9px] font-bold text-neutral-sub z-10">Me</div>
                       {(todaySchedules[1].schedule_type === 'meeting' || todaySchedules[1].attendees > 0) && (
                         <div className="h-7 w-7 rounded-full bg-neutral-divider border border-surface-card flex items-center justify-center text-[9px] font-bold text-neutral-sub">T</div>
                       )}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex w-full h-full items-center px-6">
                <span className="text-sm font-semibold text-neutral-400">No upcoming events today</span>
              </div>
            )}
            
          </div>

          <Link to="/schedules" className="w-[48px] h-[48px] ml-3 mr-1 rounded-full bg-neutral-900 flex items-center justify-center hover:bg-neutral-800 border border-neutral-800 transition-colors shadow-sm text-white focus:outline-none flex-shrink-0">
            <ArrowUpRight size={20} strokeWidth={2.5} />
          </Link>
        </div>
      </div>

      {/* Right side: Unified Utilities Box */}
      <div className="flex-1 flex justify-end">
        <div className="flex items-center gap-3 bg-surface-card border border-neutral-divider rounded-full px-2 py-1.5 shadow-sm">

          <button className="w-10 h-10 rounded-full flex items-center justify-center relative hover:bg-surface-sub transition">
            <Bell size={18} className="text-neutral-muted" />
            <span className="absolute top-2.5 right-2 w-2 h-2 bg-error rounded-full border border-surface-card" />
          </button>
          
          <div className="w-[1px] h-6 bg-neutral-divider" />

          {/* Profile Dropdown Container */}
          <div className="relative" ref={profileRef}>
            <button
              onClick={() => setIsProfileOpen(!isProfileOpen)}
              className="flex items-center gap-2 px-1 hover:bg-surface-sub rounded-full transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-surface-sub flex items-center justify-center overflow-hidden border border-neutral-divider">
                 {_user?.profile_image || _user?.profile_picture || _user?.avatar || _user?.avatar_url ? (
                   <img src={_user.profile_image || _user.profile_picture || _user.avatar || _user.avatar_url} alt="Profile" className="w-full h-full object-cover" />
                 ) : (
                   <span className="text-xs font-bold text-neutral-sub">{_user?.name?.[0] || '김'}</span>
                 )}
              </div>
              <ChevronDown size={14} className="text-neutral-400 mr-1" />
            </button>

            {/* Dropdown Menu */}
            {isProfileOpen && (
              <div className="absolute right-0 mt-3 w-56 bg-surface-card rounded-2xl shadow-[0_4px_24px_-4px_rgba(0,0,0,0.12)] border border-neutral-divider overflow-hidden z-50 py-2 animate-fade-in opacity-100">
                <div className="px-5 py-3 border-b border-neutral-divider mb-2 bg-surface-sub/50">
                  <p className="text-sm font-bold text-neutral-main tracking-tight">{_user?.name || 'User'}님</p>
                  <p className="text-xs text-neutral-muted font-medium truncate mt-0.5">{_user?.email || 'user@example.com'}</p>
                </div>

                <Link
                  to="/mypage"
                  onClick={() => setIsProfileOpen(false)}
                  className="w-full text-left px-5 py-2.5 text-sm font-semibold text-neutral-sub hover:bg-primary-50 dark:hover:bg-primary-900/20 hover:text-primary-700 flex items-center gap-3 transition-colors"
                >
                  <User size={16} className="text-neutral-muted" /> 마이페이지
                </Link>
                <div className="my-1.5 border-t border-neutral-divider" />
                
                <button 
                  onClick={() => {
                    setIsProfileOpen(false);
                    _logout();
                    navigate('/login');
                  }}
                  className="w-full text-left px-5 py-2.5 text-sm font-semibold text-error hover:bg-error-bg hover:text-error flex items-center gap-3 transition-colors"
                >
                  <LogOut size={16} className="text-error/70" /> 로그아웃
                </button>
              </div>
            )}
          </div>
          
        </div>
      </div>
      
    </header>
  );
}
