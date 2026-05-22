import { Component, type ReactNode } from "react";

interface Props { children: ReactNode; }
interface State { hasError: boolean; error: string; }

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: "" };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error: error.message };
  }

  componentDidCatch(error: Error) {
    console.error("[ErrorBoundary]", error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          background: "#1a0a0a",
          border: "1px solid #ef4444",
          borderRadius: 12,
          padding: 20,
          color: "#ef4444",
          fontFamily: "monospace",
          fontSize: 13,
        }}>
          <strong>⚠ Error en componente:</strong>
          <pre style={{ marginTop: 8, whiteSpace: "pre-wrap", color: "#fca5a5" }}>
            {this.state.error}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}
