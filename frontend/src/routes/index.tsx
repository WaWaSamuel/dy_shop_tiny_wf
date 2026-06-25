import { Routes, Route, Navigate } from 'react-router-dom';
import DashboardLayout from '@/layouts/DashboardLayout';
import ProjectLayout from '@/layouts/ProjectLayout';
import Dashboard from '@/pages/Dashboard';
import Overview from '@/pages/ecommerce/Overview';
import Products from '@/pages/ecommerce/Products';
import ProductFlow from '@/pages/ecommerce/ProductFlow';
import CreativeStudio from '@/pages/ecommerce/CreativeStudio';
import Sourcing from '@/pages/ecommerce/Sourcing';
import Orders from '@/pages/ecommerce/Orders';

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<DashboardLayout />}>
        <Route path="/" element={<Dashboard />} />
      </Route>
      <Route path="/project/ecommerce" element={<ProjectLayout />}>
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="overview" element={<Overview />} />
        <Route path="products" element={<Products />} />
        <Route path="flow/:id" element={<ProductFlow />} />
        <Route path="creative-studio" element={<CreativeStudio />} />
        <Route path="sourcing" element={<Sourcing />} />
        <Route path="orders" element={<Orders />} />
      </Route>
    </Routes>
  );
}
