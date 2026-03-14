import { useEffect, useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { uploadFile } from '../api/client'
import { useProjectStore } from '../store/useProjectStore'
import { useLang } from '../i18n/LanguageContext'
import type { ProjectInfo } from '../api/types'

const ACCEPT: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/markdown': ['.md'],
}

export default function UploadPage() {
  const navigate = useNavigate()
  const { t } = useLang()
  const setProject = useProjectStore((s) => s.setProject)
  const loadProject = useProjectStore((s) => s.loadProject)
  const reset = useProjectStore((s) => s.reset)
  const projects = useProjectStore((s) => s.projects)
  const fetchProjects = useProjectStore((s) => s.fetchProjects)

  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showContext, setShowContext] = useState(false)
  const [pendingFile, setPendingFile] = useState<File | null>(null)

  // Context form fields
  const [ctxMarket, setCtxMarket] = useState('')
  const [ctxCompetitors, setCtxCompetitors] = useState('')
  const [ctxFocus, setCtxFocus] = useState('')
  const [ctxNotes, setCtxNotes] = useState('')

  const STATUS_MAP: Record<string, { label: string; color: string }> = {
    processing: { label: t('status_processing'), color: 'text-amber-600 bg-amber-50' },
    running: { label: t('status_running'), color: 'text-blue-600 bg-blue-50' },
    completed: { label: t('status_completed'), color: 'text-green-600 bg-green-50' },
    failed: { label: t('status_failed'), color: 'text-red-600 bg-red-50' },
    pending: { label: t('status_pending'), color: 'text-gray-600 bg-gray-50' },
  }

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  const doUpload = useCallback(async (file: File, context?: Record<string, string>) => {
    setError(null)
    setUploading(true)
    try {
      reset()
      const res = await uploadFile(file, context)
      setProject(res.project_id, res.filename)
      navigate('/progress')
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || t('upload_error_default'))
    } finally {
      setUploading(false)
      setPendingFile(null)
    }
  }, [navigate, setProject, reset, t])

  const onDrop = useCallback((files: File[]) => {
    const file = files[0]
    if (!file) return
    setPendingFile(file)
    setShowContext(true)
  }, [])

  const handleUploadWithContext = async () => {
    if (!pendingFile) return
    const context: Record<string, string> = {}
    if (ctxMarket.trim()) context.market = ctxMarket.trim()
    if (ctxCompetitors.trim()) context.competitors = ctxCompetitors.trim()
    if (ctxFocus.trim()) context.focus_areas = ctxFocus.trim()
    if (ctxNotes.trim()) context.notes = ctxNotes.trim()
    await doUpload(pendingFile, Object.keys(context).length > 0 ? context : undefined)
    setShowContext(false)
    setCtxMarket('')
    setCtxCompetitors('')
    setCtxFocus('')
    setCtxNotes('')
  }

  const handleUploadDirect = async () => {
    if (!pendingFile) return
    await doUpload(pendingFile)
    setShowContext(false)
  }

  const handleOpenProject = (project: ProjectInfo) => {
    loadProject(project)
    if (project.status === 'completed') {
      navigate('/personas')
    } else if (project.status === 'running' || project.status === 'processing') {
      navigate('/progress')
    } else {
      navigate('/personas')
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPT,
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024,
    disabled: uploading,
  })

  return (
    <div className="max-w-3xl mx-auto mt-8">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">{t('upload_title')}</h2>
        <p className="text-gray-500">{t('upload_subtitle')}</p>
      </div>

      {/* Upload area */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div
          {...getRootProps()}
          className={`
            border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer
            transition-all duration-200
            ${isDragActive
              ? 'border-indigo-400 bg-indigo-50'
              : 'border-gray-300 bg-white hover:border-indigo-300 hover:bg-gray-50'
            }
            ${uploading ? 'opacity-60 cursor-not-allowed' : ''}
          `}
        >
          <input {...getInputProps()} />

          {uploading ? (
            <div>
              <div className="inline-block w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3" />
              <p className="text-gray-600">{t('upload_uploading')}</p>
            </div>
          ) : isDragActive ? (
            <p className="text-indigo-600 font-medium">{t('upload_drop_active')}</p>
          ) : (
            <div>
              <p className="text-gray-600 mb-2">
                {t('upload_hint')} <span className="text-indigo-600 font-medium">{t('upload_hint_click')}</span>
              </p>
              <p className="text-gray-400 text-sm">{t('upload_formats')}</p>
            </div>
          )}
        </div>
      </motion.div>

      {/* Context form (shown after file selection) */}
      <AnimatePresence>
        {showContext && pendingFile && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-4 overflow-hidden"
          >
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold text-gray-800">{t('upload_context_title')}</h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {t('upload_context_selected')}: {pendingFile.name} — {t('upload_context_subtitle')}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">{t('upload_market')}</label>
                  <input
                    type="text"
                    value={ctxMarket}
                    onChange={(e) => setCtxMarket(e.target.value)}
                    placeholder={t('upload_market_placeholder')}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">{t('upload_competitors')}</label>
                  <input
                    type="text"
                    value={ctxCompetitors}
                    onChange={(e) => setCtxCompetitors(e.target.value)}
                    placeholder={t('upload_competitors_placeholder')}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">{t('upload_focus')}</label>
                  <input
                    type="text"
                    value={ctxFocus}
                    onChange={(e) => setCtxFocus(e.target.value)}
                    placeholder={t('upload_focus_placeholder')}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">{t('upload_notes')}</label>
                  <input
                    type="text"
                    value={ctxNotes}
                    onChange={(e) => setCtxNotes(e.target.value)}
                    placeholder={t('upload_notes_placeholder')}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-4">
                <button
                  onClick={() => { setShowContext(false); setPendingFile(null) }}
                  className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700"
                >
                  {t('upload_cancel')}
                </button>
                <button
                  onClick={handleUploadDirect}
                  disabled={uploading}
                  className="px-4 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  {t('upload_skip')}
                </button>
                <button
                  onClick={handleUploadWithContext}
                  disabled={uploading}
                  className="px-4 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                >
                  {uploading ? t('upload_uploading_btn') : t('upload_confirm')}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm text-center"
        >
          {error}
        </motion.div>
      )}

      {/* Project history */}
      {projects.length > 0 && (
        <div className="mt-10">
          <h3 className="text-sm font-bold text-gray-700 mb-3">
            {t('upload_history_title')} ({projects.length})
          </h3>
          <div className="space-y-2">
            {projects.map((p) => {
              const st = STATUS_MAP[p.status] || STATUS_MAP.pending
              return (
                <motion.button
                  key={p.id}
                  whileHover={{ scale: 1.005 }}
                  onClick={() => handleOpenProject(p)}
                  className="w-full flex items-center gap-3 bg-white border border-gray-100 rounded-xl px-4 py-3 text-left hover:border-indigo-200 hover:shadow-sm transition-all"
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm text-gray-800 truncate">{p.name}</div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {p.filename} · {new Date(p.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  {p.context && (
                    <span className="text-[10px] bg-indigo-50 text-indigo-500 px-1.5 py-0.5 rounded shrink-0">
                      {t('upload_has_context')}
                    </span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${st.color}`}>
                    {st.label}
                  </span>
                </motion.button>
              )
            })}
          </div>
        </div>
      )}

      {/* Feature highlights */}
      <div className="mt-10 grid grid-cols-3 gap-4">
        {[
          { title: t('feature_graph_title'), desc: t('feature_graph_desc') },
          { title: t('feature_persona_title'), desc: t('feature_persona_desc') },
          { title: t('feature_report_title'), desc: t('feature_report_desc') },
        ].map((f) => (
          <div key={f.title} className="bg-white rounded-xl p-4 text-center border border-gray-100">
            <div className="font-medium text-gray-800 text-sm">{f.title}</div>
            <div className="text-gray-400 text-xs mt-1">{f.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
