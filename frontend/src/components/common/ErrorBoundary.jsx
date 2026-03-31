import { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center py-24 px-6 text-center">
          <div className="w-14 h-14 rounded-full bg-error-bg flex items-center justify-center mb-4">
            <AlertTriangle className="text-error" size={28} />
          </div>
          <h2 className="text-lg font-bold text-neutral-main mb-2">문제가 발생했습니다</h2>
          <p className="text-sm text-neutral-sub mb-6 max-w-md">
            페이지를 표시하는 중 오류가 발생했습니다. 다시 시도하거나 새로고침 해주세요.
          </p>
          <button
            onClick={this.handleReset}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary-600 text-white text-sm font-semibold hover:bg-primary-700 transition-colors"
          >
            <RefreshCw size={16} />
            다시 시도
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
