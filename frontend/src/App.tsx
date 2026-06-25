import { Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Feedback from './pages/Feedback';
import Products from './pages/Products';
import Discovery from './pages/Discovery';
import Fulfillment from './pages/Fulfillment';
import Design from './pages/Design';
import Settings from './pages/Settings';

function App() {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="aurora aurora-1" />
        <div className="aurora aurora-2" />
        <div className="aurora aurora-3" />
      </div>

      <div className="relative flex min-h-screen gap-4 p-4">
        <Sidebar />
        <main className="flex-1 overflow-y-auto rounded-[32px] border border-white/10 bg-white/5 p-6 shadow-[0_30px_80px_rgba(8,6,26,0.38)] backdrop-blur-2xl md:p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/feedback" element={<Feedback />} />
            <Route path="/products" element={<Products />} />
            <Route path="/discovery" element={<Discovery />} />
            <Route path="/fulfillment" element={<Fulfillment />} />
            <Route path="/design" element={<Design />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default App;
