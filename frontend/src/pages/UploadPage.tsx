import { useEffect, useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { uploadFile } from '../api/client'
import { useProjectStore } from '../store/useProjectStore'
import type { ProjectInfo } from '../api/types'

const ACCEPT: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/markdown': ['.md'],
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  processing: { label: '处理中', color: 'text-amber-600 bg-amber-50' },
  running: { label: '分析中', color: 'text-blue-600 bg-blue-50' },
  completed: { label: '已完成', color: 'text-green-600 bg-green-50' },
  failed: { label: '失败', color: 'text-red-600 bg-red-50' },
  pending: { label: '等待中', color: 'text-gray-600 bg-gray-50' },
}

export default function UploadPage() {
  const navigate = useNavigate()
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
      setError(e.response?.data?.detail || e.message || '上传失败，请重试')
    } finally {
      setUploading(false)
      setPendingFile(null)
    }
  }, [navigate, setProject, reset])

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
        <h2 className="text-2xl font-bold text-gray-800 mb-2">PRD 压力测试平台</h2>
        <p className="text-gray-500">
          上传产品需求文档，系统将自动生成虚拟用户并进行压力测试
        </p>
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
              <p className="text-gray-600">正在上传并解析文档...</p>
            </div>
          ) : isDragActive ? (
            <p className="text-indigo-600 font-medium">松手即可上传</p>
          ) : (
            <div>
              <p className="text-gray-600 mb-2">
                拖拽文件到这里，或 <span className="text-indigo-600 font-medium">点击选择文件</span>
              </p>
              <p className="text-gray-400 text-sm">支持 PDF、DOCX、Markdown 格式，最大 10MB</p>
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
                  <h3 className="text-sm font-bold text-gray-800">补充背景信息（可选）</h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    已选文件: {pendingFile.name} — 背景信息可帮助生成更精准的虚拟用户
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">目标市场</label>
                  <input
                    type="text"
                    value={ctxMarket}
                    onChange={(e) => setCtxMarket(e.target.value)}
                    placeholder="例如：中国一二线城市年轻白领"
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">主要竞品</label>
                  <input
                    type="text"
                    value={ctxCompetitors}
                    onChange={(e) => setCtxCompetitors(e.target.value)}
                    placeholder="例如：Notion、飞书文档、语雀"
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">重点关注</label>
                  <input
                    type="text"
                    value={ctxFocus}
                    onChange={(e) => setCtxFocus(e.target.value)}
                    placeholder="例如：新手引导流程、付费转化率"
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">备注</label>
                  <input
                    type="text"
                    value={ctxNotes}
                    onChange={(e) => setCtxNotes(e.target.value)}
                    placeholder="其他需要关注的点..."
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-4">
                <button
                  onClick={() => { setShowContext(false); setPendingFile(null) }}
                  className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700"
                >
                  取消
                </button>
                <button
                  onClick={handleUploadDirect}
                  disabled={uploading}
                  className="px-4 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  跳过，直接上传
                </button>
                <button
                  onClick={handleUploadWithContext}
                  disabled={uploading}
                  className="px-4 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                >
                  {uploading ? '上传中...' : '确认上传'}
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
            历史项目 ({projects.length})
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
                      {p.filename} · {new Date(p.created_at).toLocaleDateString('zh-CN')}
                    </div>
                  </div>
                  {p.context && (
                    <span className="text-[10px] bg-indigo-50 text-indigo-500 px-1.5 py-0.5 rounded shrink-0">
                      有背景
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
          { title: '智能图谱', desc: '自动构建产品语义知识图谱' },
          { title: '虚拟用户', desc: '生成多维度对抗性用户画像' },
          { title: '压测报告', desc: '发现设计盲区与体验瓶颈' },
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
