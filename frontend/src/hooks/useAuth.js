/**
 * 인증 훅 (팀원 E 담당)
 */
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import * as authAPI from '../api/auth'

export default function useAuth() {
  const navigate = useNavigate()
  const { setAuth, logout: storeLogout } = useAuthStore()

  const login = async (email, password) => {
    const { data } = await authAPI.login(email, password)
    setAuth({ name: data.user_name, email }, data.access_token)
    navigate('/dashboard')
  }

  const register = async (email, password, name) => {
    await authAPI.register(email, password, name)
    navigate('/login')
  }

  const logout = () => {
    storeLogout()
    navigate('/login')
  }

  return { login, register, logout }
}
