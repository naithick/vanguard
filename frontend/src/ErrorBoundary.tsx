import React from 'react';

interface Props {
    children: React.ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

class ErrorBoundary extends React.Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('React Error Boundary caught:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: '40px', fontFamily: 'monospace', background: '#fee', minHeight: '100vh' }}>
                    <h1 style={{ color: 'red', fontSize: '24px' }}>⚠️ Something went wrong</h1>
                    <pre style={{ whiteSpace: 'pre-wrap', color: '#333', marginTop: '20px', fontSize: '14px' }}>
                        {this.state.error?.message}
                    </pre>
                    <pre style={{ whiteSpace: 'pre-wrap', color: '#666', marginTop: '10px', fontSize: '12px' }}>
                        {this.state.error?.stack}
                    </pre>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
