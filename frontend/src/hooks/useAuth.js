/**
 * 인증 훅(로그인, 회원가입, 로그아웃 절차 관리) (팀원 E 담당)
 */
import { useNavigate } from 'react-router-dom'   // 화면 이동을 시켜주는 내비게이터
import useAuthStore from '../store/authStore'   // 로그인 정보를 저장하는 기억 장치 (Store)
import * as authAPI from '../api/auth'          // 실제 서버에 로그인 요청을 보내는 통로 (API)
import client from '../api/client'

export default function useAuth() {
  const navigate = useNavigate()
  const { setAuth, logout: storeLogout } = useAuthStore()

  // 1: 로그인
  const login = async (email, password) => {   // 1. 서버에 이메일과 비밀번호를 보내서 확인 받아 (비동기 통신)
    const { data } = await authAPI.login(email, password)
    sessionStorage.setItem('access_token', data.access_token)
    const { data: me } = await client.get('/auth/me')  // is_admin 포함 전체 유저 정보 로드
    setAuth(me, data.access_token)
    navigate('/dashboard')  // 3. 로그인이 완료됐으니 '대시보드' 페이지로 유저를 이동시켜
  }

  // 2: 회원가입
  const register = async (email, password, name, team) => {  // 1. 서버에 새 유저 정보를 등록해달라고 요청해
    await authAPI.register(email, password, name, team)
    // 이동은 호출부(LoginPage)에서 팝업 확인 후 처리
  }

  // 3: 로그아웃
  const logout = () => {  // 1. 기억장치 (Store)에 들어있는 유저 정보와 토큰을 싹 지워
    storeLogout()
    navigate('/login')  // 2. 아무것도 못 보게 로그인 화면으로 보내
  }

  return { login, register, logout }
}
