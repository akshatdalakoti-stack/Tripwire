import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import { ToastProvider } from './components/Toast'
import Dashboard from './pages/Dashboard'

// Heavier pages (Recharts, trace viewer) load on demand to keep the first paint small.
const AgentConfig = lazy(() => import('./pages/AgentConfig'))
const AgentEdit = lazy(() => import('./pages/AgentEdit'))
const RunView = lazy(() => import('./pages/RunView'))
const FailureReport = lazy(() => import('./pages/FailureReport'))

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <Navbar />
        <Suspense fallback={<div className="center-pad"><span className="spinner" /></div>}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/agents/new" element={<AgentConfig />} />
            <Route path="/agents/:agentId/edit" element={<AgentEdit />} />
            <Route path="/agents/:agentId/run" element={<RunView />} />
            <Route path="/agents/:agentId/report" element={<FailureReport />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </ToastProvider>
    </BrowserRouter>
  )
}
