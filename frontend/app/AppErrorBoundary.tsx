import React, { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("AppErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: "2rem",
            fontFamily: "system-ui, sans-serif",
            maxWidth: "32rem",
            margin: "2rem auto",
          }}
        >
          <h1 style={{ fontSize: "1.25rem", marginBottom: "0.5rem" }}>
            Something went wrong
          </h1>
          <p style={{ color: "#666", marginBottom: "1rem" }}>
            Try refreshing the page. If the problem persists, the app may not
            be fully supported in this browser.
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false })}
            style={{
              padding: "0.5rem 1rem",
              fontSize: "1rem",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
