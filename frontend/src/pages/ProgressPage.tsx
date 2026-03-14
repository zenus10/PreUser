import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useProjectStore } from '../store/useProjectStore'
import { useProgress } from '../hooks/useProgress'
import { useLang } from '../i18n/LanguageContext'

export default function ProgressPage() {
  const navigate = useNavigate()
  const { t } = useLang()
  const projectId = useProjectStore((s) => s.projectId)
  const progress = useProjectStore((s) => s.progress)
  const status = useProjectStore((s) => s.status)
  const fetchAnalysis = useProjectStore((s) => s.fetchAnalysis)

  const STAGES = [
    { key: 'parsing', label: t('stage_parsing_label'), desc: t('stage_parsing_desc'), icon: '📄' },
    { key: 'graph_building', label: t('stage_graph_label'), desc: t('stage_graph_desc'), icon: '🕸️' },
    { key: 'persona_generating', label: t('stage_persona_label'), desc: t('stage_persona_desc'), icon: '👤' },
    { key: 'simulating', label: t('stage_simulate_label'), desc: t('stage_simulate_desc'), icon: '🎭' },
    { key: 'reporting', label: t('stage_report_label'), desc: t('stage_report_desc'), icon: '📊' },
  ]

  useProgress()

  // Redirect to upload if no project
  useEffect(() => {
    if (!projectId) navigate('/', { replace: true })
  }, [projectId, navigate])

  // When completed, fetch analysis and navigate
  useEffect(() => {
    if (status === 'completed') {
      fetchAnalysis().then(() => navigate('/personas'))
    }
  }, [status, fetchAnalysis, navigate])

  const currentIndex = progress?.stage_index ?? 0
  const currentProgress = progress?.progress ?? 0

  return (
    <div className="max-w-2xl mx-auto mt-12">
      <div className="text-center mb-10">
        <h2 className="text-xl font-bold text-gray-800 mb-1">{t('progress_title')}</h2>
        <p className="text-gray-500 text-sm">
          {progress?.message || t('progress_preparing')}
        </p>
      </div>

      {/* Pipeline stages */}
      <div className="space-y-3">
        {STAGES.map((stage, idx) => {
          const isDone = idx < currentIndex || (idx === currentIndex && currentProgress >= 1)
          const isActive = idx === currentIndex && currentProgress < 1
          const isPending = idx > currentIndex

          return (
            <motion.div
              key={stage.key}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.1 }}
              className={`
                flex items-center gap-4 p-4 rounded-xl border transition-all duration-300
                ${isActive
                  ? 'bg-indigo-50 border-indigo-200 shadow-sm'
                  : isDone
                    ? 'bg-green-50 border-green-200'
                    : 'bg-white border-gray-100'
                }
              `}
            >
              {/* Status indicator */}
              <div className={`
                w-10 h-10 rounded-full flex items-center justify-center text-lg shrink-0
                ${isDone
                  ? 'bg-green-100'
                  : isActive
                    ? 'bg-indigo-100'
                    : 'bg-gray-100'
                }
              `}>
                {isDone ? '✅' : stage.icon}
              </div>

              {/* Label */}
              <div className="flex-1 min-w-0">
                <div className={`font-medium text-sm ${isPending ? 'text-gray-400' : 'text-gray-800'}`}>
                  {stage.label}
                </div>
                <div className="text-xs text-gray-400">{stage.desc}</div>
              </div>

              {/* Progress bar (active stage only) */}
              {isActive && (
                <div className="w-32">
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-indigo-500 rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${currentProgress * 100}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                  <div className="text-xs text-gray-400 mt-1 text-right">
                    {Math.round(currentProgress * 100)}%
                  </div>
                </div>
              )}

              {isDone && (
                <span className="text-xs text-green-600 font-medium">{t('progress_done')}</span>
              )}
            </motion.div>
          )
        })}
      </div>

      {/* Preview data */}
      {progress?.preview && Object.keys(progress.preview).length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-6 p-4 bg-white rounded-xl border border-gray-100"
        >
          <div className="text-xs text-gray-400 mb-2">{t('progress_preview_title')}</div>
          <div className="flex gap-4 flex-wrap">
            {Object.entries(progress.preview).map(([key, value]) => (
              <div key={key} className="text-center">
                <div className="text-lg font-bold text-indigo-600">{value}</div>
                <div className="text-xs text-gray-400">{key}</div>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Error state */}
      {status === 'failed' && (
        <div className="mt-6 p-4 bg-red-50 rounded-xl text-red-600 text-center text-sm">
          {t('progress_failed')}{progress?.message || t('progress_failed_unknown')}
          <button
            onClick={() => navigate('/')}
            className="block mx-auto mt-2 text-indigo-600 underline text-sm"
          >
            {t('progress_reupload')}
          </button>
        </div>
      )}
    </div>
  )
}
