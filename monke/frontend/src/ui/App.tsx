import React, { useEffect, useMemo, useRef, useState } from 'react'

type TestItem = { name: string; path: string }
type Step = { name: string; index: number; status: string; started_at?: number; ended_at?: number; duration?: number }
type RunSummary = { id: string; connector: string; status: string; progress: number; asset_logo?: string; asset_gif?: string; started_at?: number; ended_at?: number }
type RunDetail = RunSummary & { config: string; steps: Step[]; logs_tail: string[] }

const API_BASE = (import.meta as any).env?.VITE_API_BASE || ''

export function App() {
    const [tests, setTests] = useState<TestItem[]>([])
    const [runs, setRuns] = useState<RunSummary[]>([])
    const [selected, setSelected] = useState<string>('')
    const [runBusy, setRunBusy] = useState<boolean>(false)
    const [runAllBusy, setRunAllBusy] = useState<boolean>(false)
    const [runsLoading, setRunsLoading] = useState<boolean>(true)
    const [dropdownOpen, setDropdownOpen] = useState<boolean>(false)
    const dropdownRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        fetch(`${API_BASE}/api/tests`).then(r => r.json()).then(d => {
            setTests(d.tests)
            if (d.tests?.[0]) setSelected(d.tests[0].path)
        })
    }, [])

    useEffect(() => {
        let cancelled = false
        // initial snapshot
        fetch(`${API_BASE}/api/runs`).then(r => r.json()).then(d => {
            if (!cancelled) setRuns(d.runs || [])
            if (!cancelled) setRunsLoading(false)
        })
        // live updates via WS
        const proto = (API_BASE.startsWith('https') || (!API_BASE && location.protocol === 'https:')) ? 'wss' : 'ws'
        const host = API_BASE ? new URL(API_BASE, location.href).host : location.host
        const ws = new WebSocket(`${proto}://${host}/ws/runs`)
        ws.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data)
                if (msg?.bootstrap && Array.isArray(msg.runs)) {
                    setRuns(msg.runs)
                    return
                }
                const data = msg
                if (data?.id) {
                    setRuns(prev => {
                        const map = new Map(prev.map(r => [r.id, r]))
                        map.set(data.id, { ...(map.get(data.id) || data), ...data })
                        return Array.from(map.values())
                    })
                }
            } catch { }
        }
        return () => { cancelled = true; ws.close() }
    }, [])

    // Click outside handler for dropdown
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
                setDropdownOpen(false)
            }
        }
        if (dropdownOpen) {
            document.addEventListener('mousedown', handleClickOutside)
            return () => document.removeEventListener('mousedown', handleClickOutside)
        }
    }, [dropdownOpen])

    const onRun = async () => {
        if (!selected || runBusy) return
        setRunBusy(true)
        try {
            const res = await fetch(`${API_BASE}/api/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ config: selected }) })
            const { run_id } = await res.json()
            // Immediately show a placeholder card to avoid empty UI while backend warms up
            const placeholder: RunSummary = { id: run_id, connector: 'starting', status: 'queued', progress: 0 }
            setRuns(prev => [placeholder, ...prev.filter(r => r.id !== run_id)])
            // Details will be filled in by the RunCard effect and polling shortly after
        } catch (e) {
            // no-op; could add toast here
        } finally {
            setRunBusy(false)
        }
    }
    const onRunAll = async () => {
        if (runAllBusy) return
        setRunAllBusy(true)
        try {
            const res = await fetch(`${API_BASE}/api/run/all`, { method: 'POST' })
            const data = await res.json()
            const ids: string[] = data.run_ids || []
            // Show placeholders immediately
            setRuns(prev => {
                const placeholders = ids.map(id => ({ id, connector: 'starting', status: 'queued', progress: 0 } as RunSummary))
                const filtered = prev.filter(r => !ids.includes(r.id))
                return [...placeholders, ...filtered]
            })
            // Details will arrive via card fetch/polling
        } catch (e) {
        } finally {
            setRunAllBusy(false)
        }
    }

    return (
        <div className="max-w-6xl mx-auto p-6 space-y-4">
            <header className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Monke</h2>
                <div className="flex gap-2">
                    <div className="relative" ref={dropdownRef}>
                        <button
                            className="bg-[#0f1524] border border-[#24314f] rounded-lg px-3 py-2 flex items-center gap-2 min-w-[150px]"
                            onClick={() => setDropdownOpen(!dropdownOpen)}
                        >
                            {selected && (
                                <img
                                    src={`icons/${tests.find(t => t.path === selected)?.name.toLowerCase()}.svg`}
                                    className="w-4 h-4"
                                    onError={(e) => { e.currentTarget.style.display = 'none' }}
                                />
                            )}
                            <span>{tests.find(t => t.path === selected)?.name || 'Select test'}</span>
                            <span className="ml-auto">▼</span>
                        </button>
                        {dropdownOpen && (
                            <div className="absolute top-full mt-1 w-full bg-[#0f1524] border border-[#24314f] rounded-lg overflow-hidden z-10">
                                {tests.map(t => (
                                    <button
                                        key={t.path}
                                        className="w-full px-3 py-2 flex items-center gap-2 hover:bg-[#1f2a44] text-left"
                                        onClick={() => {
                                            setSelected(t.path)
                                            setDropdownOpen(false)
                                        }}
                                    >
                                        <img
                                            src={`icons/${t.name.toLowerCase()}.svg`}
                                            className="w-4 h-4"
                                            onError={(e) => { e.currentTarget.style.display = 'none' }}
                                        />
                                        <span>{t.name}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                    <button disabled={!selected || runBusy} className="px-3 py-2 rounded-lg bg-[#1f2a44] hover:opacity-90 disabled:opacity-50" onClick={onRun}>{runBusy ? 'Running…' : 'Run'}</button>
                    <button disabled={runAllBusy} className="px-3 py-2 rounded-lg bg-[#1f2a44] hover:opacity-90 disabled:opacity-50" onClick={onRunAll}>{runAllBusy ? 'Running…' : 'Run all'}</button>
                </div>
            </header>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {runsLoading && runs.length === 0 ? (
                    <div className="text-slate-400 text-sm">Loading runs…</div>
                ) : (
                    runs.map(r => <RunCard key={r.id} summary={r} />)
                )}
            </div>
        </div>
    )
}

function RunCard({ summary }: { summary: RunSummary }) {
    const [detail, setDetail] = useState<RunDetail | null>(null)
    const logsRef = useRef<HTMLPreElement>(null)
    const [wsReady, setWsReady] = useState(false)
    const detailsRef = useRef<HTMLDetailsElement>(null)
    const [logsOpen, setLogsOpen] = useState(false)
    const [copyBusy, setCopyBusy] = useState(false)
    const [copied, setCopied] = useState(false)
    const [replayBusy, setReplayBusy] = useState(false)

    const statusClass = useMemo(() => ({
        running: 'text-yellow-400', passed: 'text-green-400', failed: 'text-red-400', queued: 'text-slate-300', starting: 'text-blue-400'
    }[summary.status] || 'text-slate-300'), [summary.status])

    useEffect(() => {
        fetch(`${API_BASE}/api/runs/${summary.id}`).then(r => r.json()).then(d => {
            setDetail(d)
        })
    }, [summary.id])

    // Keep <pre> in sync with latest tail from detail (so users see logs even without WS)
    useEffect(() => {
        if (!logsRef.current) return
        const lines = detail?.logs_tail?.join('\n') || ''
        logsRef.current.textContent = lines
        logsRef.current.scrollTop = logsRef.current.scrollHeight
    }, [detail?.logs_tail])

    useEffect(() => {
        if (!logsOpen) return
        if (wsReady) return
        // Connect WS for queued or running; for completed runs we still want backlog only
        const proto = (API_BASE.startsWith('https') || (!API_BASE && location.protocol === 'https:')) ? 'wss' : 'ws'
        const host = API_BASE ? new URL(API_BASE, location.href).host : location.host
        const ws = new WebSocket(`${proto}://${host}/ws/runs/${summary.id}`)
        ws.onopen = () => setWsReady(true)
        // debounce detail refreshes to avoid flooding per-log-line
        let debounceTimer: number | undefined
        const requestDetail = () => {
            if (debounceTimer) window.clearTimeout(debounceTimer)
            debounceTimer = window.setTimeout(() => {
                fetch(`${API_BASE}/api/runs/${summary.id}`).then(r => r.json()).then(setDetail)
            }, 1500)
        }
        ws.onmessage = (e) => {
            if (logsRef.current) {
                logsRef.current.textContent += e.data + '\n'
                logsRef.current.scrollTop = logsRef.current.scrollHeight
            }
            requestDetail()
        }
        ws.onclose = () => setWsReady(false)
        return () => { if (debounceTimer) window.clearTimeout(debounceTimer); ws.close() }
    }, [summary.id, logsOpen])

    // Poll detail while run is active to keep steps fresh even if no log lines arrive
    useEffect(() => {
        if (!['queued', 'running'].includes(summary.status)) return
        let cancelled = false
        const poll = async () => {
            try {
                const r = await fetch(`${API_BASE}/api/runs/${summary.id}`)
                if (!cancelled) setDetail(await r.json())
            } catch { }
        }
        // Do an immediate poll, then continue at interval
        poll()
        const id = window.setInterval(poll, 1000)
        return () => { cancelled = true; window.clearInterval(id) }
    }, [summary.status, summary.id])

    // On transition to a terminal state, fetch one final snapshot to persist last step
    useEffect(() => {
        if (['running', 'queued'].includes(summary.status)) return
        fetch(`${API_BASE}/api/runs/${summary.id}`).then(r => r.json()).then(setDetail).catch(() => { })
    }, [summary.status, summary.id])

    const copyLogs = async () => {
        if (copyBusy) return
        const text = logsRef.current?.textContent || ''
        if (!text) return
        setCopyBusy(true)
        try {
            if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
                await navigator.clipboard.writeText(text)
            } else {
                const ta = document.createElement('textarea')
                ta.value = text
                ta.style.position = 'fixed'
                ta.style.opacity = '0'
                document.body.appendChild(ta)
                ta.focus()
                ta.select()
                try { document.execCommand('copy') } catch { }
                document.body.removeChild(ta)
            }
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1200)
        } finally {
            setCopyBusy(false)
        }
    }

    const handleReplay = async () => {
        if (!detail?.config || replayBusy) return
        setReplayBusy(true)
        try {
            // Extract relative config path from full path
            const configPath = detail.config.includes('configs/')
                ? detail.config.substring(detail.config.indexOf('configs/'))
                : detail.config

            const res = await fetch(`${API_BASE}/api/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config: configPath })
            })
            const { run_id } = await res.json()

            // Update the summary with the new run_id to replace this card
            summary.id = run_id
            summary.status = 'queued'
            summary.progress = 0

            // Reset detail to trigger fresh load
            setDetail(null)
            setLogsOpen(false)
            if (logsRef.current) {
                logsRef.current.textContent = ''
            }
        } catch (e) {
            console.error('Failed to replay test:', e)
        } finally {
            setReplayBusy(false)
        }
    }

    return (
        <div className="bg-[#12192a] border border-[#1d2740] rounded-xl p-3">
            <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-medium text-slate-200">{summary.connector} Test</div>
                <div className="flex items-center gap-2">
                    {summary.status === 'failed' && (
                        <button
                            onClick={handleReplay}
                            disabled={replayBusy}
                            className="text-xs px-2 py-1 rounded bg-[#1f2a44] hover:opacity-90 disabled:opacity-50 flex items-center gap-1"
                        >
                            {replayBusy ? 'Replaying...' : '🔄 Replay'}
                        </button>
                    )}
                    <div className={`text-xs bg-[#1f2a44] px-2 py-1 rounded-full ${statusClass}`}>{summary.status}</div>
                </div>
            </div>
            <div className="relative overflow-hidden rounded-lg border border-[#24314f] h-24">
                {summary.asset_logo && (
                    <img
                        className="absolute top-2 left-2 w-8 h-8 bg-white p-1 rounded-md shadow ring-1 ring-slate-200"
                        src={`${summary.asset_logo.startsWith('/') ? '' : '/'}${summary.asset_logo}`}
                    />
                )}
                {/* Monkey GIF next to logo */}
                <img
                    className="absolute top-2 left-12 w-8 h-8 rounded-md shadow"
                    src={pickGif(summary.id)}
                    alt="Monkey"
                />
                <div className="w-full h-full grid place-items-center text-3xl">
                    {detail?.status === 'failed' ? '❌' : detail?.status === 'passed' ? '🎉' : '🐒'}
                </div>
            </div>
            <div className="flex items-center justify-between mt-2">
                <div className="text-xs text-slate-400">{summary.connector}</div>
                <div className="text-xs text-slate-500">{summary.id.slice(0, 8)}</div>
            </div>
            <div className="flex gap-2 flex-wrap my-2">
                {detail?.steps?.map(s => (
                    <div key={s.index} className={`text-xs px-2 py-1 rounded-full border ${stepClass(s.status)}`}>{s.name}</div>
                ))}
            </div>
            <div className="h-2 rounded-full border border-[#24314f] overflow-hidden bg-[#0f1524]">
                <div className="h-full bg-gradient-to-r from-purple-600 to-cyan-400" style={{ width: `${Math.round((detail?.progress ?? summary.progress) * 100)}%` }} />
            </div>
            <details ref={detailsRef} onToggle={() => setLogsOpen(!!detailsRef.current?.open)} className="mt-2 bg-[#0f1524] border border-[#24314f] rounded-lg p-2">
                <summary>
                    Logs
                    <button
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); copyLogs() }}
                        disabled={copyBusy}
                        className="float-right text-xs px-2 py-1 rounded bg-[#1f2a44] hover:opacity-90 disabled:opacity-50"
                    >
                        {copied ? 'Copied!' : 'Copy logs'}
                    </button>
                </summary>
                <pre ref={logsRef} className="text-xs text-slate-300 whitespace-pre-wrap max-h-72 overflow-auto">{detail?.logs_tail?.join('\n') || ''}</pre>
            </details>
        </div>
    )
}

function stepClass(status: string) {
    if (status === 'running') return 'border-yellow-500 text-yellow-400'
    if (status === 'passed') return 'border-green-500 text-green-400'
    if (status === 'failed') return 'border-red-500 text-red-400'
    return 'border-[#24314f] text-slate-300'
}

function pickGif(runId: string): string {
    // deterministic pick from 3 gifs based on run id hash
    let hash = 0
    for (let i = 0; i < runId.length; i++) {
        hash = ((hash << 3) - hash) + runId.charCodeAt(i)
        hash |= 0
    }
    const idx = Math.abs(hash) % 3 + 1
    return `gifs/monkey${idx}.gif`
}
