import { AppRoutes } from './routes';

function App() {
  return (
    <div className="app-shell">
      <div className="app-orb app-orb-a" />
      <div className="app-orb app-orb-b" />
      <div className="app-orb app-orb-c" />
      <AppRoutes />
    </div>
  );
}

export default App;
