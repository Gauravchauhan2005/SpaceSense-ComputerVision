import React, { useState, useEffect } from 'react';
import { BarChart3, Download, Play, Square, Plus, Award, Activity, Cpu } from 'lucide-react';
import { api } from '../services/api';
import { MetricCard } from '../components/MetricCard';
import type { EvaluationReport } from '../types';

export const Evaluation: React.FC = () => {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState(false);

  // Reference entry form
  const [refType, setRefType] = useState<'distance' | 'angle'>('distance');
  const [estimatedVal, setEstimatedVal] = useState<number>(55.0);
  const [groundTruthVal, setGroundTruthVal] = useState<number>(50.0);

  const fetchEvaluation = async () => {
    try {
      const data = await api.getEvaluation();
      setReport(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchEvaluation();
    const timer = setInterval(fetchEvaluation, 3000);
    return () => clearInterval(timer);
  }, []);

  const handleAddReference = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      await api.addEvaluationReference(refType, estimatedVal, groundTruthVal);
      await fetchEvaluation();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStartStability = async () => {
    try {
      await api.startStabilityRecording();
      await fetchEvaluation();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleStopStability = async () => {
    try {
      await api.stopStabilityRecording();
      await fetchEvaluation();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const distAcc = report?.distance_accuracy;
  const angleAcc = report?.angle_accuracy;
  const stab = report?.stability;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Computer Vision System Evaluation</h2>
          <p className="text-xs text-[#9BA7B5]">Quantitative benchmarks for model latency, error analysis & jitter stability</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => window.open('/api/evaluation/export', '_blank')}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#181D24] text-[#E8EDF4] border border-[#2A313B] hover:border-[#53B7FF] rounded-lg text-xs font-medium transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-[#53B7FF]" />
            <span>Export Metrics (CSV)</span>
          </button>
        </div>
      </div>

      {/* Latency & Hardware Performance Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Average Pipeline FPS"
          value={report?.fps_mean ? report.fps_mean.toFixed(1) : '—'}
          unit="FPS"
          icon={Activity}
          subtitle={`Current: ${report?.fps_current?.toFixed(1) ?? '—'}`}
        />
        <MetricCard
          title="Mean Inference Latency"
          value={report?.latency_mean_ms ? report.latency_mean_ms.toFixed(1) : '—'}
          unit="ms"
          icon={Cpu}
          subtitle={`Median: ${report?.latency_median_ms?.toFixed(1) ?? '—'} ms`}
        />
        <MetricCard
          title="95th %tile Latency"
          value={report?.latency_p95_ms ? report.latency_p95_ms.toFixed(1) : '—'}
          unit="ms"
          icon={Cpu}
          subtitle={`99th: ${report?.latency_p99_ms?.toFixed(1) ?? '—'} ms`}
        />
        <MetricCard
          title="Face Availability"
          value={report?.face_availability_pct ? `${report.face_availability_pct.toFixed(0)}%` : '—'}
          icon={Award}
          subtitle={`Hands: ${report?.hand_availability_pct?.toFixed(0) ?? 0}%`}
        />
      </div>

      {/* Accuracy Benchmarking: Distance & Angles */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Distance Benchmark */}
        <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[#E8EDF4]">Distance Estimation Accuracy</h3>
            <span className="text-xs font-mono text-[#53B7FF]">
              N = {distAcc?.measurements ?? 0} paired samples
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-[#101318] p-3 rounded-lg border border-[#2A313B]">
              <span className="text-[11px] uppercase text-[#9BA7B5] block mb-1">MAE</span>
              <span className="text-lg font-bold font-mono text-[#37C98B]">
                {distAcc?.mean_abs_error !== undefined ? `${distAcc.mean_abs_error.toFixed(2)} cm` : '—'}
              </span>
            </div>
            <div className="bg-[#101318] p-3 rounded-lg border border-[#2A313B]">
              <span className="text-[11px] uppercase text-[#9BA7B5] block mb-1">RMSE</span>
              <span className="text-lg font-bold font-mono text-[#53B7FF]">
                {distAcc?.rmse !== undefined ? `${distAcc.rmse.toFixed(2)} cm` : '—'}
              </span>
            </div>
            <div className="bg-[#101318] p-3 rounded-lg border border-[#2A313B]">
              <span className="text-[11px] uppercase text-[#9BA7B5] block mb-1">Max Error</span>
              <span className="text-lg font-bold font-mono text-[#FFB547]">
                {distAcc?.max_error !== undefined ? `${distAcc.max_error.toFixed(2)} cm` : '—'}
              </span>
            </div>
          </div>
          <p className="text-xs text-[#9BA7B5]">
            Calculated by comparing estimated distances with verified ground-truth tape measurements.
          </p>
        </div>

        {/* Angle Benchmark */}
        <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[#E8EDF4]">Geometric Angle Accuracy</h3>
            <span className="text-xs font-mono text-[#37C98B]">
              N = {angleAcc?.measurements ?? 0} paired samples
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-[#101318] p-3 rounded-lg border border-[#2A313B]">
              <span className="text-[11px] uppercase text-[#9BA7B5] block mb-1">Mean Error</span>
              <span className="text-lg font-bold font-mono text-[#37C98B]">
                {angleAcc?.mean_error !== undefined ? `${angleAcc.mean_error.toFixed(2)}°` : '—'}
              </span>
            </div>
            <div className="bg-[#101318] p-3 rounded-lg border border-[#2A313B]">
              <span className="text-[11px] uppercase text-[#9BA7B5] block mb-1">Median Error</span>
              <span className="text-lg font-bold font-mono text-[#53B7FF]">
                {angleAcc?.mean_abs_error !== undefined ? `${angleAcc.mean_abs_error.toFixed(2)}°` : '—'}
              </span>
            </div>
            <div className="bg-[#101318] p-3 rounded-lg border border-[#2A313B]">
              <span className="text-[11px] uppercase text-[#9BA7B5] block mb-1">Max Error</span>
              <span className="text-lg font-bold font-mono text-[#FFB547]">
                {angleAcc?.max_error !== undefined ? `${angleAcc.max_error.toFixed(2)}°` : '—'}
              </span>
            </div>
          </div>
          <p className="text-xs text-[#9BA7B5]">
            Evaluates vector angle formula θ = arccos((BA·BC)/(|BA|·|BC|)) against benchmark angles.
          </p>
        </div>
      </div>

      {/* Ground Truth Ingestion & Stability Recording */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Ground Truth Entry Form */}
        <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-3">
          <h3 className="text-sm font-semibold text-[#E8EDF4] flex items-center gap-2">
            <Plus className="w-4 h-4 text-[#53B7FF]" />
            Record Ground-Truth Reference Pair
          </h3>
          <p className="text-xs text-[#9BA7B5]">
            Enter an actual physical tape-measured distance or angle to update the MAE/RMSE benchmark table.
          </p>

          <form onSubmit={handleAddReference} className="space-y-3 pt-1">
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="text-[11px] text-[#9BA7B5] block mb-1">Metric Type</label>
                <select
                  value={refType}
                  onChange={(e) => setRefType(e.target.value as any)}
                  className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-2.5 py-1.5 text-xs text-[#E8EDF4]"
                >
                  <option value="distance">Distance (cm)</option>
                  <option value="angle">Angle (deg)</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] text-[#9BA7B5] block mb-1">CV Estimate</label>
                <input
                  type="number"
                  step="0.1"
                  value={estimatedVal}
                  onChange={(e) => setEstimatedVal(parseFloat(e.target.value) || 0)}
                  className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-2.5 py-1.5 text-xs font-mono text-[#E8EDF4]"
                />
              </div>
              <div>
                <label className="text-[11px] text-[#9BA7B5] block mb-1">Ground Truth</label>
                <input
                  type="number"
                  step="0.1"
                  value={groundTruthVal}
                  onChange={(e) => setGroundTruthVal(parseFloat(e.target.value) || 0)}
                  className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-2.5 py-1.5 text-xs font-mono text-[#E8EDF4]"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#2A313B] hover:bg-[#3B4452] text-[#E8EDF4] font-medium py-2 rounded-lg text-xs transition-colors"
            >
              Add Verification Measurement
            </button>
          </form>
        </div>

        {/* Stationary Jitter Stability Evaluation */}
        <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[#E8EDF4]">Stationary Tracking Jitter</h3>
            {report?.is_recording_stability ? (
              <span className="flex items-center gap-1.5 text-xs text-[#FF5C65] font-mono animate-pulse">
                <span className="w-2 h-2 rounded-full bg-[#FF5C65]" />
                RECORDING STABILITY...
              </span>
            ) : (
              <span className="text-xs text-[#9BA7B5] font-mono">IDLE</span>
            )}
          </div>
          <p className="text-xs text-[#9BA7B5]">
            Keep your face or hand still for 5 seconds while recording to compute coordinate standard deviation (jitter amplitude in pixels).
          </p>

          <div className="grid grid-cols-2 gap-3 py-1">
            <div className="bg-[#101318] p-3 rounded-lg border border-[#2A313B] text-center">
              <span className="text-[11px] uppercase text-[#9BA7B5] block">Jitter σ</span>
              <span className="text-lg font-bold font-mono text-[#53B7FF]">
                {stab ? `${stab.jitter.toFixed(3)} px` : '—'}
              </span>
            </div>
            <div className="bg-[#101318] p-3 rounded-lg border border-[#2A313B] text-center">
              <span className="text-[11px] uppercase text-[#9BA7B5] block">Samples</span>
              <span className="text-lg font-bold font-mono text-[#E8EDF4]">{stab?.samples ?? 0}</span>
            </div>
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={handleStartStability}
              disabled={report?.is_recording_stability}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-[#37C98B]/20 text-[#37C98B] border border-[#37C98B]/30 hover:bg-[#37C98B]/30 rounded-lg text-xs font-semibold disabled:opacity-40"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Start Stability Test</span>
            </button>
            <button
              onClick={handleStopStability}
              disabled={!report?.is_recording_stability}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-[#FF5C65]/20 text-[#FF5C65] border border-[#FF5C65]/30 hover:bg-[#FF5C65]/30 rounded-lg text-xs font-semibold disabled:opacity-40"
            >
              <Square className="w-3.5 h-3.5" />
              <span>Stop & Compute</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
