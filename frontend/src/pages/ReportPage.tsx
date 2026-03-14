import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie,
} from 'recharts'
import { useProjectStore } from '../store/useProjectStore'

const SEVERITY_BADGE: Record<string, string> = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  low: 'bg-gray-100 text-gray-600',
}

const PIE_COLORS = ['#ef4444', '#f59e0b', '#6366f1', '#10b981', '#8b5cf6', '#ec4899']

export default function ReportPage() {
  const navigate = useNavigate()
  const projectId = useProjectStore((s) => s.projectId)
  const report = useProjectStore((s) => s.report)
  const fetchAnalysis = useProjectStore((s) => s.fetchAnalysis)
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (!projectId) { navigate('/', { replace: true }); return }
    if (!report) fetchAnalysis()
  }, [projectId, navigate, report, fetchAnalysis])

  if (!report) {
    return <div className="flex items-center justify-center h-64 text-gray-400">加载中...</div>
  }

  const churnData = Object.entries(report.churn_attribution).map(([key, val]) => ({
    name: key,
    value: val,
  }))

  const npsColor = report.nps_average >= 7 ? 'text-green-600' : report.nps_average >= 5 ? 'text-amber-600' : 'text-red-600'

  const satEntries = Object.entries(report.satisfaction_matrix)
  const satData = satEntries.map(([feature, scores]) => {
    const vals = Object.values(scores as Record<string, number>)
    const avg = vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : 0
    return { feature, avg: Math.round(avg * 10) / 10 }
  }).sort((a, b) => a.avg - b.avg)

  const toggleSection = (i: number) => {
    setExpandedSections((prev) => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i)
      else next.add(i)
      return next
    })
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-12">
      {/* Header with NPS */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-800">压力测试报告</h2>
          <p className="text-sm text-gray-500 mt-1">
            发现 {report.blind_spots.length} 个设计盲区 · {report.bottlenecks.length} 个体验瓶颈 · {report.assumption_risks.length} 个假设风险
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/chat?mode=report_qa')}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            追问报告
          </button>
          <div className="text-center">
            <div className={`text-3xl font-bold ${npsColor}`}>{report.nps_average.toFixed(1)}</div>
            <div className="text-xs text-gray-400">模拟 NPS</div>
          </div>
        </div>
      </div>

      {/* Executive Summary */}
      {report.executive_summary && (
        <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-2xl border border-indigo-100 p-6">
          <h3 className="text-sm font-bold text-indigo-700 uppercase tracking-wider mb-3">Executive Summary</h3>
          <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {report.executive_summary}
          </div>
        </div>
      )}

      {/* Report Sections (v2.0) */}
      {report.sections && report.sections.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-base font-bold text-gray-800">详细报告章节</h3>
          {report.sections.map((section, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              <button
                onClick={() => toggleSection(i)}
                className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50"
              >
                <span className="font-medium text-gray-800">{section.title}</span>
                <span className="text-gray-400 text-sm">{expandedSections.has(i) ? '收起' : '展开'}</span>
              </button>
              {expandedSections.has(i) && (
                <div className="px-4 pb-4 border-t border-gray-50">
                  <div className="text-sm text-gray-700 whitespace-pre-wrap mt-3 leading-relaxed">
                    {section.content}
                  </div>
                  {section.reasoning_trace && (
                    <details className="mt-3">
                      <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
                        推理过程
                      </summary>
                      <p className="text-xs text-gray-500 mt-1 bg-gray-50 rounded p-2 whitespace-pre-wrap">
                        {section.reasoning_trace}
                      </p>
                    </details>
                  )}
                  {section.data_references.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {section.data_references.map((ref, j) => (
                        <span key={j} className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                          {ref}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-6">
        {satData.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">功能满意度均值</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={satData} layout="vertical" margin={{ left: 60 }}>
                <XAxis type="number" domain={[0, 10]} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="feature" tick={{ fontSize: 11 }} width={80} />
                <Tooltip />
                <Bar dataKey="avg" radius={[0, 4, 4, 0]} name="满意度">
                  {satData.map((entry, i) => (
                    <Cell key={i} fill={entry.avg >= 7 ? '#10b981' : entry.avg >= 5 ? '#f59e0b' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {churnData.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">流失归因分布</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={churnData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {churnData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Blind Spots */}
      <Section title="设计盲区发现" count={report.blind_spots.length} icon="?">
        {report.blind_spots.map((bs, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="bg-white rounded-xl border border-gray-100 p-4"
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <h4 className="font-medium text-gray-800">{bs.title}</h4>
              <span className="text-xs text-gray-400 shrink-0">
                影响 {bs.affected_personas.length} 个角色
              </span>
            </div>
            <p className="text-sm text-gray-600 mb-3">{bs.description}</p>
            {bs.evidence.length > 0 && (
              <div className="mb-3">
                <span className="text-xs text-gray-400">证据：</span>
                {bs.evidence.map((e, j) => (
                  <p key={j} className="text-xs text-gray-500 italic ml-2">"{e}"</p>
                ))}
              </div>
            )}
            <div className="bg-green-50 rounded-lg px-3 py-2">
              <span className="text-xs text-green-700 font-medium">建议：</span>
              <p className="text-sm text-green-700">{bs.recommendation}</p>
            </div>
          </motion.div>
        ))}
      </Section>

      {/* Bottlenecks */}
      <Section title="体验瓶颈排序" count={report.bottlenecks.length} icon="!">
        {report.bottlenecks.map((bn, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="bg-white rounded-xl border border-gray-100 p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEVERITY_BADGE[bn.severity] || SEVERITY_BADGE.low}`}>
                {bn.severity}
              </span>
              <h4 className="font-medium text-gray-800">{bn.title}</h4>
              <span className="text-xs text-gray-400 ml-auto">
                {bn.affected_count} 人受影响 · {bn.stage}阶段
              </span>
            </div>
            <p className="text-sm text-gray-600 mb-2">{bn.description}</p>
            {bn.quotes.length > 0 && (
              <div className="space-y-1">
                {bn.quotes.map((q, j) => (
                  <p key={j} className="text-xs text-gray-500 italic">"{q}"</p>
                ))}
              </div>
            )}
          </motion.div>
        ))}
      </Section>

      {/* Assumption Risks */}
      <Section title="假设风险清单" count={report.assumption_risks.length} icon="!">
        {report.assumption_risks.map((ar, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            className="bg-white rounded-xl border border-gray-100 p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEVERITY_BADGE[ar.risk_level] || SEVERITY_BADGE.low}`}>
                {ar.risk_level}
              </span>
              <h4 className="font-medium text-gray-800 text-sm">{ar.assumption}</h4>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-2">
              <div className="bg-gray-50 rounded-lg p-2">
                <span className="text-xs text-gray-400">反面证据</span>
                <p className="text-sm text-gray-600">{ar.counter_evidence}</p>
              </div>
              <div className="bg-red-50 rounded-lg p-2">
                <span className="text-xs text-red-400">如果假设不成立</span>
                <p className="text-sm text-red-700">{ar.if_wrong}</p>
              </div>
            </div>
          </motion.div>
        ))}
      </Section>
    </div>
  )
}

function Section({
  title,
  count,
  icon,
  children,
}: {
  title: string
  count: number
  icon: string
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">{icon}</span>
        <h3 className="text-base font-bold text-gray-800">{title}</h3>
        <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{count}</span>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  )
}
