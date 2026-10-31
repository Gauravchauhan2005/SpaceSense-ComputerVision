import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  Activity,
  Move,
  Crosshair,
  BarChart3,
  Clock,
  Settings,
  Camera,
  Play,
  Square,
  Sparkles,
} from 'lucide-react';
import { StatusBadge } from './StatusBadge';
import { api } from '../services/api';
import type { ConnectionStatus } from '../types';

interface LayoutProps {
  status: ConnectionStatus;
  fps?: number;
  isClientStreaming?: boolean;
  onStartCamera?: () => Promise<void>;
  onStopCamera?: () => void;
}

export const Layout: React.FC<LayoutProps> = ({
  status,
  fps = 0,
  isClientStreaming = false,
  onStartCamera,
  onStopCamera,
}) => {
  const [cameraBusy, setCameraBusy] = useState(false);

  const handleStartCamera = async () => {
    try {
      setCameraBusy(true);
      if (onStartCamera) {
        await onStartCamera();
      } else {
        await api.startCamera(0, [640, 480]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setCameraBusy(false);
    }
  };

  const handleStopCamera = async () => {
    try {
      setCameraBusy(true);
      if (onStopCamera) {
        onStopCamera();
      } else {
        await api.stopCamera();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setCameraBusy(false);
    }
  };

  const navItems = [
    { to: '/', label: 'Live Monitor', icon: Activity },
    { to: '/motion', label: 'Motion Analysis', icon: Move },
    { to: '/calibration', label: 'Calibration', icon: Crosshair },
    { to: '/evaluation', label: 'Evaluation', icon: BarChart3 },
    { to: '/history', label: 'Session History', icon: Clock },
    { to: '/settings', label: 'Settings', icon: Settings },
  ];

  return (
    <div className="flex h-screen w-screen bg-[#101318] text-[#E8EDF4] overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-[#181D24] border-r border-[#2A313B] flex flex-col justify-between flex-shrink-0 z-20">
        <div>
          {/* Logo / Brand */}
          <div className="p-5 border-b border-[#2A313B] flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#53B7FF] to-[#0070F3] flex items-center justify-center text-[#101318] shadow-lg shadow-[#53B7FF]/20">
              <Sparkles className="w-5 h-5 fill-current" />
            </div>
            <div>
              <h1 className="font-bold text-base tracking-wide flex items-center gap-1.5">
                SpaceSense <span className="text-xs px-1.5 py-0.5 rounded bg-[#53B7FF]/20 text-[#53B7FF] font-mono">CV</span>
              </h1>
              <p className="text-[11px] text-[#9BA7B5]">Spatial & Ergonomics</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-[#53B7FF]/15 text-[#53B7FF] border border-[#53B7FF]/30'
                      : 'text-[#9BA7B5] hover:text-[#E8EDF4] hover:bg-[#2A313B]/40'
                  }`
                }
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Sidebar Footer: Camera Controls & Status */}
        <div className="p-4 border-t border-[#2A313B] space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[#9BA7B5]">Backend Stream</span>
            <StatusBadge status={status} />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={handleStartCamera}
              disabled={cameraBusy || isClientStreaming}
              className="flex items-center justify-center gap-1.5 px-3 py-2 bg-[#37C98B]/20 text-[#37C98B] hover:bg-[#37C98B]/30 border border-[#37C98B]/40 rounded-lg text-xs font-semibold transition-all disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{isClientStreaming ? 'Running' : 'Start'}</span>
            </button>
            <button
              onClick={handleStopCamera}
              disabled={cameraBusy || (!isClientStreaming && status !== 'connected')}
              className="flex items-center justify-center gap-1.5 px-3 py-2 bg-[#FF5C65]/20 text-[#FF5C65] hover:bg-[#FF5C65]/30 border border-[#FF5C65]/40 rounded-lg text-xs font-semibold transition-all disabled:opacity-50"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Stop</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Top Header */}
        <header className="h-14 bg-[#181D24] border-b border-[#2A313B] px-6 flex items-center justify-between flex-shrink-0 z-10">
          <div className="flex items-center gap-4 text-xs font-mono text-[#9BA7B5]">
            <span>SYSTEM: <span className="text-[#37C98B]">ONLINE</span></span>
            <span>•</span>
            <span>LOCAL INFERENCE: <span className="text-[#53B7FF]">ACTIVE</span></span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-[#101318] px-3 py-1.5 rounded-lg border border-[#2A313B] text-xs font-mono">
              <Activity className="w-3.5 h-3.5 text-[#53B7FF]" />
              <span>FPS: <strong className="text-[#E8EDF4]">{fps.toFixed(1)}</strong></span>
            </div>
            <StatusBadge status={status} pulse={status === 'connected'} />
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6 bg-[#101318]">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
