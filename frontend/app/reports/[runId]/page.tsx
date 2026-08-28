'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { BrandMark } from '@/components/app-shell';
import { PredictionResults } from '@/components/prediction-results';
import type { PredictionResult } from '@/lib/research-types';

export default function SharedReportPage() {
  const params = useParams<{ runId: string | string[] }>();
  const router = useRouter();
  const runId = Array.isArray(params.runId) ? params.runId[0] : params.runId;
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    const controller = new AbortController();

    async function loadReport() {
      try {
        const response = await fetch(`/api/qianscope/v1/predictions/${encodeURIComponent(runId)}`, {
          cache: 'no-store',
          signal: controller.signal,
        });
        const body = await response.json() as PredictionResult & { detail?: string };
        if (!response.ok) throw new Error(body.detail || '报告不存在或已归档。');
        if (!cancelled) setResult(body);
      } catch (reason) {
        if (cancelled || (reason instanceof DOMException && reason.name === 'AbortError')) return;
        if (!cancelled) setError(reason instanceof Error ? reason.message : '报告暂时无法读取。');
      }
    }

    void loadReport();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [runId]);

  if (result) {
    return <PredictionResults result={result} onNew={() => router.push('/predict')} />;
  }

  return (
    <main className="report-route-state" id="main-content">
      <BrandMark />
      <span>黔镜 · QIANSCOPE REPORT</span>
      <h1>{error ? '这份报告暂时无法打开' : '正在还原已封存的推演报告'}</h1>
      <p>{error || `运行 ${runId || '—'} · 正在读取模型、数据与结果快照。`}</p>
      {error ? <button type="button" onClick={() => router.push('/predict')}>创建新的预测</button> : <i aria-hidden="true" />}
    </main>
  );
}
