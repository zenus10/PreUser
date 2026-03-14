import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useProjectStore } from '../store/useProjectStore'

const NAV_ITEMS = [
  { to: '/', label: '上传 PRD', icon: '📄', always: true },
  { to: '/progress', label: '分析进度', icon: '⏳', always: false },
  { to: '/graph', label: '知识图谱', icon: '🔗', always: false },
  { to: '/personas', label: '虚拟用户', icon: '👥', always: false },
  { to: '/narratives', label: '体验叙事', icon: '📖', always: false },
  { to: '/report', label: '压测报告', icon: '📊', always: false },
  { to: '/chat', label: '深度交互', icon: '💬', always: false },
]

export default function Layout() {
  const projectId = useProjectStore((s) => s.projectId)
  const status = useProjectStore((s) => s.status)
  const filename = useProjectStore((s) => s.filename)
  const location = useLocation()

  const isCompleted = status === 'completed'

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top bar */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-indigo-600">PreUser v2.0</h1>
          <span className="text-xs text-gray-400">PRD 自动化压力测试平台</span>
        </div>
        {filename && (
          <span className="text-sm text-gray-500 truncate max-w-xs">
            {filename}
          </span>
        )}
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar nav */}
        <nav className="w-52 bg-white border-r border-gray-200 py-4 shrink-0">
          <ul className="space-y-1 px-2">
            {NAV_ITEMS.map((item) => {
              const disabled = !item.always && !projectId
              const show = item.always || projectId
              if (!show) return null

              return (
                <li key={item.to}>
                  <NavLink
                    to={disabled ? '#' : item.to}
                    onClick={(e) => disabled && e.preventDefault()}
                    className={({ isActive }) =>
                      `flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                        isActive && location.pathname === item.to
                          ? 'bg-indigo-50 text-indigo-700 font-medium'
                          : disabled
                            ? 'text-gray-300 cursor-not-allowed'
                            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                      }`
                    }
                  >
                    <span>{item.icon}</span>
                    <span>{item.label}</span>
                    {item.to === '/personas' && !isCompleted && status && status !== 'failed' && (
                      <span className="ml-auto w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                    )}
                  </NavLink>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
