/**
 * 유틸리티 함수 (팀원 E 담당)
 */

export function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('ko-KR')
}

export function formatDateTime(dateStr) {
  return new Date(dateStr).toLocaleString('ko-KR')
}

export function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}
