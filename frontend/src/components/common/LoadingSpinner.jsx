const sizes = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10' };

export default function LoadingSpinner({ size = 'md' }) {
  return (
    <div className={`${sizes[size]} border-2 border-primary-100 border-t-primary-500 rounded-full animate-spin`} />
  );
}
