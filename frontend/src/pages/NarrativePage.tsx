import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { useProjectStore } from '../store/useProjectStore'
import type { SimulationResult } from '../api/types'

const OUTCOME_LABELS: Record<string, { label: string; color: string }> = {
  completed: { label: '完成', color: 'text-green-600' },
  churned: { label: '流失', color: 'text-red-600' },
  confused: { label: '困惑', color: 'text-amber-600' },
  evaluating: { label: '观望', color: 'text-blue-600' },
  inactive: { label: '沉默', color: 'text-gray-600' },
}

const SCENE_LABELS: Record<string, string> = {
  first_use: '首次体验',
  deep_use: '深度使用',
  competitor: '竞品对比',
  churn: '流失前夕',
}

const SEVERITY_COLORS: Record<string, string> = {
  high: 'bg-red-100 text-red-700 border-red-200',
  medium: 'bg-amber-100 text-amber-700 border-amber-200',
  low: 'bg-gray-100 text-gray-600 border-gray-200',
}

export default function NarrativePage() {
  const navigate = useNavigate()
  const projectId = useProjectStore((s) => s.projectId)
  const personas = useProjectStore((s) => s.personas)
  const simulations = useProjectStore((s) => s.simulations)
  const fetchAnalysis = useProjectStore((s) => s.fetchAnalysis)
  const [selectedIdx, setSelectedIdx] = useState<number>(0)

  useEffect(() => {
    if (!projectId) { navigate('/', { replace: true }); return }
    if (simulations.length === 0) fetchAnalysis()
  }, [projectId, navigate, simulations.length, fetchAnalysis])

  const sim = simulations[selectedIdx]
  const persona = sim ? personas.find((p) => p.persona_id === sim.persona_id) : undefined

  if (simulations.length === 0) {
    return <div className="flex items-center justify-center h-64 text-gray-400">加载中...</div>
  }

  const emotionData = sim?.emotion_curve.map((val, idx) => ({
    step: `步骤${idx + 1}`,
    emotion: val,
  })) ?? []

  const outcomeInfo = sim ? OUTCOME_LABELS[sim.outcome] || { label: sim.outcome, color: 'text-gray-600' } : null

  return (
    <div className="flex gap-6 h-full">
      {/* Persona + scene tabs */}
      <div className="w-52 shrink-0 overflow-y-auto">
        <h3 className="text-xs font-semibold text-gray-400 uppercase mb-3">仿真结果</h3>
        <div className="space-y-1">
          {simulations.map((s, i) => {
            const p = personas.find((pp) => pp.persona_id === s.persona_id)
            const isActive = i === selectedIdx
            const sceneName = SCENE_LABELS[s.scene] || s.scene || '首次体验'
            return (
              <button
                key={i}
                onClick={() => setSelectedIdx(i)}
                className={`
                  w-full text-left px-3 py-2 rounded-lg text-sm transition-colors
                  ${isActive
                    ? 'bg-indigo-50 text-indigo-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-50'
                  }
                `}
              >
                <div className="truncate">{p?.name || s.persona_id}</div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] bg-gray-100 text-gray-500 px-1 rounded">
                    {sceneName}
                  </span>
                  <span className={`text-xs ${OUTCOME_LABELS[s.outcome]?.color || ''}`}>
                    {OUTCOME_LABELS[s.outcome]?.label || s.outcome}
                  </span>
                  <span className="text-xs text-gray-400">NPS {s.nps_score}</span>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Main content */}
      {sim && (
        <motion.div
          key={selectedIdx}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex-1 overflow-y-auto space-y-6"
        >
          {/* Header */}
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-bold">{persona?.name || sim.persona_id}</h2>
            <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded">
              {SCENE_LABELS[sim.scene] || sim.scene || '首次体验'}
            </span>
            <span className={`text-sm font-medium ${outcomeInfo?.color}`}>{outcomeInfo?.label}</span>
            <span className="text-sm text-gray-400">NPS: {sim.nps_score}/10</span>
            <button
              onClick={() => navigate(`/chat?mode=interview&persona=${sim.persona_id}`)}
              className="ml-auto text-xs px-2 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700"
            >
              与 TA 对话
            </button>
          </div>

          {/* Emotion curve */}
          {emotionData.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">情绪曲线</h3>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={emotionData}>
                  <XAxis dataKey="step" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <ReferenceLine y={50} stroke="#e5e7eb" strokeDasharray="3 3" />
                  <Line
                    type="monotone"
                    dataKey="emotion"
                    stroke="#6366f1"
                    strokeWidth={2}
                    dot={{ r: 4, fill: '#6366f1' }}
                    name="情绪值"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Action logs (v2.0) */}
          {sim.action_logs && sim.action_logs.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                行为日志 ({sim.action_logs.length} 步)
              </h3>
              <div className="space-y-1.5 max-h-60 overflow-y-auto">
                {sim.action_logs.map((log, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className="text-gray-400 w-6 text-right shrink-0">#{log.step}</span>
                    <span className="font-mono text-indigo-600 w-32 shrink-0">{log.action}</span>
                    <span className="text-gray-500 flex-1 truncate">{log.thought}</span>
                    {log.friction && (
                      <span className={`text-[10px] px-1 rounded ${
                        log.friction.severity === 'high' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                      }`}>
                        {log.friction.type}
                      </span>
                    )}
                    <span className={`w-8 text-right ${
                      log.emotion >= 0.7 ? 'text-green-600' : log.emotion >= 0.4 ? 'text-amber-600' : 'text-red-600'
                    }`}>
                      {(log.emotion * 100).toFixed(0)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Narrative */}
          <div className="bg-white rounded-xl border border-gray-100 p-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">第一人称叙事</h3>
            <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {sim.narrative}
            </div>
          </div>

          {/* Friction points */}
          {sim.friction_points.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                摩擦点 ({sim.friction_points.length})
              </h3>
              <div className="space-y-3">
                {sim.friction_points.map((fp, i) => (
                  <div
                    key={i}
                    className={`rounded-lg border p-3 ${SEVERITY_COLORS[fp.severity] || SEVERITY_COLORS.low}`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold uppercase">{fp.severity}</span>
                      <span className="text-xs opacity-75">{fp.type}</span>
                    </div>
                    <p className="text-sm">{fp.description}</p>
                    {fp.quote && (
                      <p className="text-xs italic mt-1 opacity-75">"{fp.quote}"</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* NPS & willingness */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <h4 className="text-xs font-semibold text-gray-400 mb-1">NPS 理由</h4>
              <p className="text-sm text-gray-700">{sim.nps_reason}</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-100 p-4">
              <h4 className="text-xs font-semibold text-gray-400 mb-1">3天后是否回来</h4>
              <p className="text-sm text-gray-700">
                {sim.willingness_to_return.will_return ? 'Yes' : 'No'} — {sim.willingness_to_return.reason}
              </p>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}
