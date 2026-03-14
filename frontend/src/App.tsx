import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import UploadPage from './pages/UploadPage'
import ProgressPage from './pages/ProgressPage'
import PersonaPage from './pages/PersonaPage'
import NarrativePage from './pages/NarrativePage'
import ReportPage from './pages/ReportPage'
import ChatPage from './pages/ChatPage'
import GraphPage from './pages/GraphPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<UploadPage />} />
        <Route path="/progress" element={<ProgressPage />} />
        <Route path="/personas" element={<PersonaPage />} />
        <Route path="/narratives" element={<NarrativePage />} />
        <Route path="/report" element={<ReportPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/graph" element={<GraphPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
