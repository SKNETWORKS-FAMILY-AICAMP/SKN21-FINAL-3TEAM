/**
 * 로딩 스피너 (팀원 E 담당)
 */
export default function LoadingSpinner({ size = 'md' }) {
  const sizeClass = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  }[size]

  return (
    <div className={`${sizeClass} animate-spin rounded-full border-2 border-gray-200 border-t-primary`} />
  )
}
