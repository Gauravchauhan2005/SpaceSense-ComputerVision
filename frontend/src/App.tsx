import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { LiveMonitor } from './pages/LiveMonitor';
import { MotionAnalysis } from './pages/MotionAnalysis';
import { Calibration } from './pages/Calibration';
import { Evaluation } from './pages/Evaluation';
import { SessionHistory } from './pages/SessionHistory';
import { SettingsPage } from './pages/SettingsPage';
import { useWebSocket } from './hooks/useWebSocket';

export const App: React.FC = () => {
  const {
    trackingData,
    frameData,
    status,
    history,
    isClientStreaming,
    startClientCamera,
    stopClientCamera,
  } = useWebSocket();

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <Layout
              status={status}
              fps={trackingData?.fps ?? 0}
              isClientStreaming={isClientStreaming}
              onStartCamera={startClientCamera}
              onStopCamera={stopClientCamera}
            />
          }
        >
          <Route index element={<LiveMonitor trackingData={trackingData} frameData={frameData} history={history} />} />
          <Route path="motion" element={<MotionAnalysis trackingData={trackingData} frameData={frameData} />} />
          <Route path="calibration" element={<Calibration frameData={frameData} trackingData={trackingData} />} />
          <Route path="evaluation" element={<Evaluation />} />
          <Route path="history" element={<SessionHistory />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};
