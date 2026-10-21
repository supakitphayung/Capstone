import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Layout } from './app/Layout';
import { OverviewPage } from './pages/OverviewPage';
import { ScriptPage } from './pages/ScriptPage';
import { HistoryPage } from './pages/HistoryPage';
import { ResultPage } from './pages/ResultPage';
import { GuidePage } from './pages/GuidePage';
import './styles.css';

createRoot(document.getElementById('root')!).render(<StrictMode><BrowserRouter><Routes>
  <Route element={<Layout />}>
    <Route index element={<OverviewPage />} />
    <Route path="scripts/:scriptId" element={<ScriptPage />} />
    <Route path="history" element={<HistoryPage />} />
    <Route path="jobs/:jobId" element={<HistoryPage />} />
    <Route path="results/:resultId" element={<ResultPage />} />
    <Route path="guide" element={<GuidePage />} />
    <Route path="*" element={<div className="card p-12">ไม่พบหน้านี้ <a className="text-link" href="/">กลับหน้าภาพรวม</a></div>} />
  </Route>
</Routes></BrowserRouter></StrictMode>);
