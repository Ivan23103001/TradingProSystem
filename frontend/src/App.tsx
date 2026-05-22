import { ErrorBoundary } from "./components/ErrorBoundary";
import Dashboard from "./components/Dashboard";

function App() {
  return (
    <ErrorBoundary>
      <Dashboard />
    </ErrorBoundary>
  );
}

export default App;
