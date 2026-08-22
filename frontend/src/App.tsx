import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import AgentConfig from './pages/AgentConfig'
import RunView from './pages/RunView'
import FailureReport from './pages/FailureReport'

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/agents/new" element={<AgentConfig />} />
        <Route path="/agents/:agentId/run" element={<RunView />} />
        <Route path="/agents/:agentId/report" element={<FailureReport />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
