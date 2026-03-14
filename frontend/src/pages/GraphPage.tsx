import { useState, useCallback, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeMouseHandler,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useProjectStore } from '../store/useProjectStore'
import type { GraphNode, GraphEdge, Conflict } from '../api/types'

// Node type colors
const TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  scene: { bg: '#EFF6FF', border: '#3B82F6', text: '#1D4ED8' },
  role: { bg: '#F0FDF4', border: '#22C55E', text: '#15803D' },
  action: { bg: '#FFF7ED', border: '#F97316', text: '#C2410C' },
  touchpoint: { bg: '#FAF5FF', border: '#A855F7', text: '#7E22CE' },
  constraint: { bg: '#FEF2F2', border: '#EF4444', text: '#B91C1C' },
  emotion_expect: { bg: '#FDF4FF', border: '#D946EF', text: '#A21CAF' },
}

const DEFAULT_COLOR = { bg: '#F9FAFB', border: '#9CA3AF', text: '#374151' }

export default function GraphPage() {
  const analysis = useProjectStore((s) => s.analysis)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [showConflicts, setShowConflicts] = useState(true)

  const graphData = analysis?.graph
  if (!graphData) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        请先完成分析以查看知识图谱
      </div>
    )
  }

  const rawNodes: GraphNode[] = graphData.nodes || []
  const rawEdges: GraphEdge[] = [...(graphData.edges || []), ...(graphData.new_edges || [])]
  const conflicts: Conflict[] = graphData.conflicts || []

  // Build conflict entity set
  const conflictEntities = useMemo(() => {
    const set = new Set<string>()
    conflicts.forEach((c) => c.involved_entities.forEach((e) => set.add(e)))
    return set
  }, [conflicts])

  // Layout: simple grid layout with some randomization based on type
  const typeGroups: Record<string, GraphNode[]> = {}
  rawNodes.forEach((n) => {
    const type = n.type || 'unknown'
    if (!typeGroups[type]) typeGroups[type] = []
    typeGroups[type].push(n)
  })

  const flowNodes: Node[] = useMemo(() => {
    const nodes: Node[] = []
    const typeOrder = Object.keys(typeGroups)
    typeOrder.forEach((type, typeIdx) => {
      const group = typeGroups[type]
      group.forEach((n, idx) => {
        const colors = TYPE_COLORS[type] || DEFAULT_COLOR
        const isConflict = conflictEntities.has(n.id)

        nodes.push({
          id: n.id,
          position: {
            x: 150 + (idx % 6) * 220 + (typeIdx % 2) * 100,
            y: 80 + typeIdx * 200 + Math.floor(idx / 6) * 120,
          },
          data: {
            label: (
              <div className="text-center">
                <div className="text-xs font-bold" style={{ color: colors.text }}>
                  {n.name}
                </div>
                <div className="text-[10px] text-gray-500 mt-0.5">{type}</div>
                {isConflict && showConflicts && (
                  <div className="text-[10px] text-red-600 font-bold mt-0.5">!</div>
                )}
              </div>
            ),
          },
          style: {
            background: colors.bg,
            border: `2px solid ${isConflict && showConflicts ? '#EF4444' : colors.border}`,
            borderRadius: 8,
            padding: '6px 10px',
            fontSize: 12,
            minWidth: 80,
            boxShadow: isConflict && showConflicts ? '0 0 8px rgba(239,68,68,0.3)' : undefined,
          },
        })
      })
    })
    return nodes
  }, [rawNodes, conflictEntities, showConflicts])

  const flowEdges: Edge[] = useMemo(() => {
    return rawEdges.map((e, i) => ({
      id: `e-${i}`,
      source: e.from_id,
      target: e.to_id,
      label: e.relation_type,
      type: 'default',
      animated: e.confidence < 0.6,
      style: {
        opacity: Math.max(0.3, e.confidence),
        strokeWidth: e.confidence > 0.8 ? 2 : 1,
      },
      labelStyle: { fontSize: 9, fill: '#9CA3AF' },
      markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12 },
    }))
  }, [rawEdges])

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges)

  const onNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      const gn = rawNodes.find((n) => n.id === node.id)
      setSelectedNode(gn || null)
    },
    [rawNodes]
  )

  // Find edges connected to selected node
  const relatedEdges = selectedNode
    ? rawEdges.filter((e) => e.from_id === selectedNode.id || e.to_id === selectedNode.id)
    : []

  // Find conflicts involving selected node
  const relatedConflicts = selectedNode
    ? conflicts.filter((c) => c.involved_entities.includes(selectedNode.id))
    : []

  return (
    <div className="flex h-full gap-4">
      {/* Graph canvas */}
      <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-700">
            知识图谱 ({rawNodes.length} 实体, {rawEdges.length} 关系)
          </h2>
          <div className="flex items-center gap-4">
            {/* Legend */}
            <div className="flex items-center gap-2 text-[10px]">
              {Object.entries(TYPE_COLORS).map(([type, colors]) => (
                <span key={type} className="flex items-center gap-0.5">
                  <span
                    className="w-2.5 h-2.5 rounded-sm"
                    style={{ background: colors.border }}
                  />
                  {type}
                </span>
              ))}
            </div>
            <label className="flex items-center gap-1 text-xs text-gray-500">
              <input
                type="checkbox"
                checked={showConflicts}
                onChange={(e) => setShowConflicts(e.target.checked)}
                className="rounded"
              />
              显示冲突
            </label>
          </div>
        </div>
        <div style={{ height: 'calc(100% - 40px)' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
            minZoom={0.2}
            maxZoom={2}
          >
            <Background />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const gn = rawNodes.find((rn) => rn.id === n.id)
                return (TYPE_COLORS[gn?.type || ''] || DEFAULT_COLOR).border
              }}
            />
          </ReactFlow>
        </div>
      </div>

      {/* Detail panel */}
      <div className="w-80 bg-white rounded-xl border border-gray-200 overflow-y-auto shrink-0">
        {selectedNode ? (
          <div className="p-4 space-y-4">
            <div>
              <div
                className="text-xs font-medium px-2 py-0.5 rounded inline-block"
                style={{
                  background: (TYPE_COLORS[selectedNode.type] || DEFAULT_COLOR).bg,
                  color: (TYPE_COLORS[selectedNode.type] || DEFAULT_COLOR).text,
                }}
              >
                {selectedNode.type}
              </div>
              <h3 className="text-lg font-bold text-gray-900 mt-1">{selectedNode.name}</h3>
              <p className="text-sm text-gray-600 mt-1">{selectedNode.description}</p>
              <p className="text-xs text-gray-400 mt-1">
                来源: {selectedNode.source_block_id}
              </p>
            </div>

            {/* Related edges */}
            {relatedEdges.length > 0 && (
              <div>
                <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
                  关联关系 ({relatedEdges.length})
                </h4>
                <div className="space-y-1.5">
                  {relatedEdges.map((e, i) => {
                    const isSource = e.from_id === selectedNode.id
                    const otherNode = rawNodes.find(
                      (n) => n.id === (isSource ? e.to_id : e.from_id)
                    )
                    return (
                      <div
                        key={i}
                        className="text-xs p-2 bg-gray-50 rounded cursor-pointer hover:bg-gray-100"
                        onClick={() => otherNode && setSelectedNode(otherNode)}
                      >
                        <span className="text-gray-500">
                          {isSource ? '→' : '←'} {e.relation_type}
                        </span>{' '}
                        <span className="font-medium text-gray-700">
                          {otherNode?.name || (isSource ? e.to_id : e.from_id)}
                        </span>
                        <span className="text-gray-400 ml-1">
                          ({(e.confidence * 100).toFixed(0)}%)
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Related conflicts */}
            {relatedConflicts.length > 0 && (
              <div>
                <h4 className="text-xs font-bold text-red-500 uppercase tracking-wider mb-2">
                  冲突 ({relatedConflicts.length})
                </h4>
                <div className="space-y-2">
                  {relatedConflicts.map((c, i) => (
                    <div key={i} className="text-xs p-2 bg-red-50 rounded border border-red-100">
                      <div className="flex items-center gap-1.5 mb-1">
                        <span
                          className={`px-1 py-0.5 rounded text-[10px] font-bold ${
                            c.severity === 'high'
                              ? 'bg-red-200 text-red-800'
                              : c.severity === 'medium'
                                ? 'bg-yellow-200 text-yellow-800'
                                : 'bg-gray-200 text-gray-800'
                          }`}
                        >
                          {c.severity}
                        </span>
                        <span className="text-red-700 font-medium">{c.type}</span>
                      </div>
                      <p className="text-red-600">{c.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="p-4 text-center text-gray-400 text-sm">
            点击图谱中的节点查看详情
          </div>
        )}
      </div>
    </div>
  )
}
