import React, { useState, useEffect } from 'react';
import { Clock, Download, Trash2, Play, Square, RefreshCw, AlertTriangle } from 'lucide-react';
import { api } from '../services/api';
import type { SessionSummary } from '../types';

export const SessionHistory: React.FC = () => {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchSessions = async () => {
    try {
      const res = await api.getSessions();
      setSessions(res.sessions || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const handleStartSession = async () => {
    try {
      setLoading(true);
      const res = await api.startSession();
      setActiveSession(res.session_id || 'active');
      await fetchSessions();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStopSession = async () => {
    try {
      setLoading(true);
      await api.stopSession();
      setActiveSession(null);
      await fetchSessions();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSession = async (id: string) => {
    if (!confirm('Are you sure you want to delete this recorded session?')) return;
    try {
      await api.deleteSession(id);
      await fetchSessions();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Ergonomic Session History</h2>
          <p className="text-xs text-[#9BA7B5]">Logged distance profiles, warning counts & posture duration metrics</p>
        </div>

        <div className="flex items-center gap-2">
          {activeSession ? (
            <button
              onClick={handleStopSession}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#FF5C65]/20 text-[#FF5C65] border border-[#FF5C65]/40 hover:bg-[#FF5C65]/30 rounded-lg text-xs font-semibold transition-colors"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>End Active Session</span>
            </button>
          ) : (
            <button
              onClick={handleStartSession}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#37C98B]/20 text-[#37C98B] border border-[#37C98B]/40 hover:bg-[#37C98B]/30 rounded-lg text-xs font-semibold transition-colors"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Record New Session</span>
            </button>
          )}

          <button
            onClick={fetchSessions}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#181D24] text-[#9BA7B5] hover:text-[#E8EDF4] border border-[#2A313B] rounded-lg text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Sessions Table */}
      <div className="bg-[#181D24] rounded-xl border border-[#2A313B] overflow-hidden">
        {sessions.length === 0 ? (
          <div className="p-12 text-center text-[#9BA7B5]">
            <Clock className="w-10 h-10 mx-auto mb-2 opacity-40 text-[#53B7FF]" />
            <p className="text-sm font-semibold">No recorded sessions yet</p>
            <p className="text-xs text-[#9BA7B5] mt-1">Start a tracking session to log ergonomic telemetry</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#101318]/70 border-b border-[#2A313B] text-[#9BA7B5] uppercase tracking-wider font-semibold">
                  <th className="py-3 px-4">Session ID</th>
                  <th className="py-3 px-4">Date & Time</th>
                  <th className="py-3 px-4">Duration</th>
                  <th className="py-3 px-4">Avg Distance</th>
                  <th className="py-3 px-4">Warnings</th>
                  <th className="py-3 px-4">Critical Events</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2A313B]/50 font-mono">
                {sessions.map((s) => (
                  <tr key={s.session_id} className="hover:bg-[#2A313B]/20 transition-colors">
                    <td className="py-3 px-4 font-bold text-[#53B7FF]">#{s.session_id}</td>
                    <td className="py-3 px-4 text-[#E8EDF4]">
                      {new Date(s.start_time * 1000).toLocaleString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                    <td className="py-3 px-4 text-[#9BA7B5]">{Math.round(s.duration_seconds)}s</td>
                    <td className="py-3 px-4">
                      {s.avg_distance_cm ? (
                        <span className="text-[#37C98B] font-semibold">{s.avg_distance_cm.toFixed(1)} cm</span>
                      ) : (
                        <span className="text-[#9BA7B5]">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {s.warning_count > 0 ? (
                        <span className="text-[#FFB547] font-semibold flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          {s.warning_count}
                        </span>
                      ) : (
                        <span className="text-[#37C98B]">0</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {s.critical_count > 0 ? (
                        <span className="text-[#FF5C65] font-semibold">{s.critical_count}</span>
                      ) : (
                        <span className="text-[#37C98B]">0</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <a
                          href={api.exportSessionUrl(s.session_id)}
                          download
                          className="p-1.5 text-[#53B7FF] hover:bg-[#53B7FF]/10 rounded transition-colors"
                          title="Export CSV"
                        >
                          <Download className="w-4 h-4" />
                        </a>
                        <button
                          onClick={() => handleDeleteSession(s.session_id)}
                          className="p-1.5 text-[#FF5C65] hover:bg-[#FF5C65]/10 rounded transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
