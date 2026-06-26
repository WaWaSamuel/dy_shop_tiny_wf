import { AppRoutes } from './routes';

function App() {
  return (
    <div className="app-shell">
      <div className="app-orb app-orb-a" />
      <div className="app-orb app-orb-b" />
      <div className="app-orb app-orb-c" />
      <div className="app-sticker app-sticker-chiikawa" />
      <div className="app-sticker app-sticker-usagi" />
      <div className="app-sticker app-sticker-momonga" />
      <AppRoutes />
    </div>
  );
}

export default App;
