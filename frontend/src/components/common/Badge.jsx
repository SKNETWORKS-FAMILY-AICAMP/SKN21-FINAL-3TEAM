const variants = {
  intent: 'bg-primary-50 text-primary-700',
  document: 'bg-accent-50 text-accent-700',
  schedule: 'bg-success-bg text-success',
  'priority-high': 'bg-error-bg text-error',
  'priority-medium': 'bg-warning-bg text-warning',
  'priority-low': 'bg-success-bg text-success',
  'risk-high': 'bg-error-bg text-error',
  'risk-medium': 'bg-warning-bg text-warning',
  'risk-low': 'bg-success-bg text-success',
  'confidence-high': 'bg-success-bg text-success',
  'confidence-mid': 'bg-warning-bg text-warning',
  'confidence-low': 'bg-error-bg text-error',
  'status-active': 'bg-success-bg text-success',
  'status-revising': 'bg-warning-bg text-warning',
  'status-scheduled': 'bg-info-bg text-info',
  'status-completed': 'bg-success-bg text-success',
  'status-in-progress': 'bg-warning-bg text-warning',
  'role-admin': 'bg-accent-50 text-accent-700',
  'role-user': 'bg-primary-50 text-primary-700',
};

export default function Badge({ variant = 'intent', children, className = '' }) {
  return (
    <span className={`badge ${variants[variant] || variants.intent} ${className}`}>
      {children}
    </span>
  );
}
